# Notes for future sessions

- Before writing new stories or changing the upload queue, read `docs/LEARNINGS.md` (what works for this channel) and the latest files in `stats/`.
- New story packs need a `hook:` line per story; check with `python -m reelbot.cli lint --general --require-hook stories/packNN.txt` (kids packs: `lint --require-hook`).
- YouTube uploads run from the owner's phone (`phone/phone_uploader.py`, queue `phone/uploads.json`, never re-uploads). Metricool is no longer used.
- Videos are hosted on the `reels` branch (zip: https://github.com/sandeepnair0808/malayalam-bot/archive/refs/heads/reels.zip).
