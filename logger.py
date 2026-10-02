#!/usr/bin/env python3
"""Log the live headcount of Stadthallenbad Wien.

The only public source is a Twitch stream (twitch.tv/wienersportstaetten) that
broadcasts a Grafana gauge. We grab one frame, OCR the number, and cross-check
it against the gauge bar's angle. Gauge scale (measured): 0-1000, yellow from
~700 ("kritisch"), red from ~850 ("Sperre").

Appends one row per run to the CSV given as first argument (default data.csv):
    timestamp, count, gauge_estimate, status, note
"""
import csv
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

CHANNEL = "https://www.twitch.tv/wienersportstaetten"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("data.csv")
# Earliest opening / latest closing across the week; outside this we don't sample.
SAMPLE_FROM, SAMPLE_TO = 6 * 60 + 15, 21 * 60 + 45

# Gauge geometry measured on a 1152x648 frame; scaled for other sizes.
REF_W, REF_H = 1152, 648
CX, CY, R = 575.5, 466.4, 273.4
START_DEG, END_DEG = 198.0, -18.0   # angle of value 0 and value MAX
MAX = 1000
YELLOW, RED = 700, 850


def grab_frame(path):
    url = subprocess.run(
        ["yt-dlp", "--no-update", "-q", "-g", "-f", "best", CHANNEL],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    if not url:
        return False
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", url, "-frames:v", "1", path],
        check=True, timeout=60,
    )
    return True


def is_bar(p):
    r, g, b = p
    return (g > 150 and r < 140 and b < 130) or (r > 200 and g > 150 and b < 100) or (r > 200 and g < 110)


def gauge_estimate(im):
    """Walk along the thick value bar from the 0 end; return value where it stops."""
    sx, sy = im.width / REF_W, im.height / REF_H
    last = None
    deg = START_DEG - 0.5  # step inside the bar's end cap
    while deg >= END_DEG:
        a = math.radians(deg)
        x = round((CX + (R - 20) * math.cos(a)) * sx)
        y = round((CY - (R - 20) * math.sin(a)) * sy)
        if not is_bar(im.getpixel((x, y))):
            break
        last = deg
        deg -= 0.2
    if last is None:
        return 0
    return round((START_DEG - last) / (START_DEG - END_DEG) * MAX)


def ocr_count(im):
    if not shutil.which("tesseract"):
        return None
    sx, sy = im.width / REF_W, im.height / REF_H
    crop = im.convert("L").crop((int(450 * sx), int(430 * sy), int(700 * sx), int(530 * sy)))
    crop = ImageOps.invert(crop).point(lambda v: 0 if v < 170 else 255)
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        crop.save(f.name)
        txt = subprocess.run(
            ["tesseract", f.name, "-", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789"],
            capture_output=True, text=True,
        ).stdout.strip()
    return int(txt) if txt.isdigit() else None


def status(n):
    if n is None:
        return ""
    return "red" if n >= RED else "yellow" if n >= YELLOW else "green"


def main():
    now = datetime.now().astimezone()
    if not SAMPLE_FROM <= now.hour * 60 + now.minute <= SAMPLE_TO:
        print("outside opening hours, skipping")
        return
    ts = now.isoformat(timespec="seconds")
    row = [ts, "", "", "", ""]
    with tempfile.TemporaryDirectory() as d:
        frame = f"{d}/frame.png"
        try:
            ok = grab_frame(frame)
        except Exception as e:
            ok, row[4] = False, f"error: {e}"[:200]
        if not ok:
            row[4] = row[4] or "offline"
        else:
            im = Image.open(frame).convert("RGB")
            n, est = ocr_count(im), gauge_estimate(im)
            # OCR is primary; flag it if it disagrees badly with the bar.
            # OCR is primary; without it the gauge bar (+-3) stands in.
            note = ""
            if n is None:
                n, note = est, "gauge only"
            elif abs(n - est) > 40:
                note = "ocr/gauge mismatch"
            row = [ts, n, est, status(n), note]
    new = not OUT.exists()
    with OUT.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "count", "gauge_estimate", "status", "note"])
        w.writerow(row)
    print(",".join(map(str, row)))


if __name__ == "__main__":
    sys.exit(main())
