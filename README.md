# Stadthallenbad crowd

How full is Stadthallenbad Wien, and when is it quiet?

The pool publishes its live headcount only as a Twitch stream of a Grafana gauge
(scale 0–1000; yellow "kritisch" from ~700, red "Sperre" from ~850).

- `logger.py` grabs one frame of the stream (yt-dlp + ffmpeg), reads the number with
  tesseract and cross-checks it against the gauge bar's angle. Appends one CSV row.
- `.github/workflows/collect.yml` runs it every 5 minutes during opening hours and
  commits the row to the `data` branch (`data.csv`).
- `docs/index.html` is the dashboard (GitHub Pages). It loads the CSV from the `data`
  branch in the browser and computes everything client-side. Test locally with
  `?data=some.csv`.

No AI anywhere in the pipeline.
