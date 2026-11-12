# Notes for future sessions

- Before writing new stories or changing the upload queue, read `docs/LEARNINGS.md` (what works for this channel) and the latest files in `stats/`.
- New story packs need a `hook:` line per story; check with `python -m reelbot.cli lint --general --require-hook stories/packNN.txt` (kids packs: `lint --require-hook`).
- YouTube uploads run from the owner's phone (`phone/phone_uploader.py`, queue `phone/uploads.json`, never re-uploads). Metricool is no longer used.
- Videos are hosted on the `reels` branch (zip: https://github.com/sandeepnair0808/malayalam-bot/archive/refs/heads/reels.zip).
- Natural voice: ElevenLabs (connector). Use eleven_v4 with voices Vijayesh F6apuaOciIF8axVr21FB (male) and Samitha OVkoEbwxsYHiSRMFV9t3 (female), 1 take per story, tags [curious]/[pause]/[softly]/[long pause]. The free tier runs one generation at a time and is often busy. This machine cannot download elevenlabsusercontent.com: put the links in `el_get.sh` on the reels branch, the phone downloads them, and the user attaches the mp3s. Then run `tools/el_align.py` (scene boundaries) and `tools/el_build.py` (render with that audio).
- Uploads: the phone uploader enforces a 4 h gap and 7:00-21:59 (see docs/LEARNINGS.md). Never post hourly.
