"""Voice a story with Sarvam AI (Bulbul) on the phone, one line at a time.

    cd ~/malayalam-bot && git pull && cd phone
    python sarvam_voice.py --test                                 # 1 short sample per voice, listen and choose
    python sarvam_voice.py ../stories/lockdown/part1_lines.json   # full story -> Download/sarvam/<chapter>.wav

The API key is asked once and kept only on this phone (phone/sarvam_key.txt, never uploaded).
Each chapter becomes one WAV with a 1.5 s gap between lines, so the video can be synced exactly.
Tries Bulbul v3 voices first and falls back to Bulbul v2 if Sarvam rejects them.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave
from getpass import getpass
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY_FILE = HERE / "sarvam_key.txt"
OUT = Path("/sdcard/Download/sarvam")
API = "https://api.sarvam.ai/text-to-speech"
GAP = 1.5  # seconds of silence between lines
RATE = 24000

# Role -> candidate (model, speaker, pace). The first one Sarvam accepts is used and remembered.
CANDIDATES = {
    "narrator": [("bulbul:v3", "aditya", 0.95), ("bulbul:v3", "rahul", 0.95), ("bulbul:v3", "shubh", 0.95),
                 ("bulbul:v2", "abhilash", 0.95)],
    "pappa": [("bulbul:v3", "ratan", 0.9), ("bulbul:v3", "kabir", 0.9), ("bulbul:v3", "amit", 0.9),
              ("bulbul:v2", "karun", 0.9)],
    "mummy": [("bulbul:v3", "kavitha", 0.95), ("bulbul:v3", "ritu", 0.95), ("bulbul:v3", "priya", 0.95),
              ("bulbul:v2", "vidya", 0.95)],
    "neighbour": [("bulbul:v3", "rohan", 1.0), ("bulbul:v3", "dev", 1.0), ("bulbul:v2", "hitesh", 1.0)],
}
CHOSEN_FILE = HERE / "sarvam_voices.json"


def key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    k = getpass("Paste your Sarvam API key (hidden, saved only on this phone): ").strip()
    KEY_FILE.write_text(k)
    os.chmod(KEY_FILE, 0o600)
    return k


def call(text: str, model: str, speaker: str, pace: float) -> bytes:
    body = {"text": text, "target_language_code": "ml-IN", "speaker": speaker, "model": model,
            "pace": pace, "speech_sample_rate": RATE}
    if model.endswith("v2"):
        body["enable_preprocessing"] = True
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "api-subscription-key": key()})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            return b"".join(base64.b64decode(a) for a in data["audios"])
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:  # rate limited: wait and retry
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"{e.code} {e.read()[:300].decode(errors='replace')}") from e
    raise RuntimeError("rate limited")


def voice_for(role: str, sample_text: str) -> tuple:
    chosen = json.loads(CHOSEN_FILE.read_text()) if CHOSEN_FILE.exists() else {}
    if role in chosen:
        return tuple(chosen[role])
    last = None
    for cand in CANDIDATES.get(role, CANDIDATES["narrator"]):
        try:
            call(sample_text[:60], *cand)
            chosen[role] = list(cand)
            CHOSEN_FILE.write_text(json.dumps(chosen))
            print(f"  {role}: {cand[1]} ({cand[0]})")
            return cand
        except RuntimeError as err:
            last = err
            if str(err).startswith(("401", "403")):
                raise SystemExit(f"Sarvam refused the key: {err}\nDelete phone/sarvam_key.txt and run again.")
    raise SystemExit(f"No voice accepted for {role}: {last}")


def frames(wav_bytes: bytes) -> tuple[bytes, tuple]:
    """PCM data and its format (channels, sample width, rate)."""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.readframes(w.getnframes()), (w.getnchannels(), w.getsampwidth(), w.getframerate())


def write_wav(path: Path, pcm: bytes, fmt: tuple) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(fmt[0])
        w.setsampwidth(fmt[1])
        w.setframerate(fmt[2])
        w.writeframes(pcm)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["--test"]:
        sample = "ഇന്ന് ട്രെയിൻ ഇല്ലെടാ. നമുക്ക് നാട്ടിൽ പോകാം."
        for role in CANDIDATES:
            model, spk, pace = voice_for(role, sample)
            write_wav(OUT / f"test_{role}_{spk}.wav", *frames(call(sample, model, spk, pace)))
        print(f"Samples saved in {OUT}. Listen; if you like them, run the full story.")
        return 0
    story = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for ch in story:
        dest = OUT / f"{ch['chapter']}.wav"
        if dest.exists():
            print(f"{dest.name} already done")
            continue
        pcm, fmt = b"", None
        for i, line in enumerate(ch["lines"], 1):
            model, spk, pace = voice_for(line["voice"], line["text"])
            data, f = frames(call(line["text"], model, spk, pace))
            if fmt and f != fmt:
                raise SystemExit(f"voices returned different audio formats {fmt} vs {f}; delete phone/sarvam_voices.json "
                                 "and edit CANDIDATES so all roles use the same model")
            fmt = f
            gap = b"\x00" * (int(fmt[2] * GAP) * fmt[0] * fmt[1])
            pcm += (gap if pcm else b"") + data
            print(f"  {ch['chapter']} {i}/{len(ch['lines'])}")
        write_wav(dest, pcm, fmt)
        print(f"OK {dest}")
    print(f"\nDone. Attach the files in Download/sarvam (not the test_ ones) in the chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
