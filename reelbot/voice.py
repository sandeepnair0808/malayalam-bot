"""Malayalam voice-over.

Providers:
- edge: Microsoft Edge neural voices via `edge-tts` (ml-IN-SobhanaNeural / ml-IN-MidhunNeural). Free, natural.
- gtts: Google Translate TTS via `gTTS` (lang="ml"). Free, more robotic.
- none: no narration; scenes get a fixed reading duration from the subtitle length.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def reading_time(text: str) -> float:
    """Seconds a viewer needs to read a Malayalam subtitle without narration."""
    return max(2.5, min(6.0, 1.2 + len(text) * 0.09))


async def _edge(text: str, voice: str, out: Path) -> None:
    import edge_tts

    # edge-tts uses aiohttp, which ignores proxy env vars unless told explicitly.
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    await edge_tts.Communicate(text, voice, rate="-5%", proxy=proxy).save(str(out))


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="ml").save(str(out))


def synthesize(settings: Settings, text: str, out: Path) -> Path | None:
    """Write narration audio for one line. Returns None when narration is disabled."""
    provider = settings.tts.lower()
    if provider == "none":
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    if provider == "edge":
        try:
            asyncio.run(_edge(text, settings.voice, out))
            return out
        except Exception as err:
            log.warning("edge-tts failed (%s); falling back to gTTS", err)
    _gtts(text, out)
    return out


def narrate(settings: Settings, lines: list[str], workdir: Path) -> list[tuple[Path | None, float]]:
    """Synthesize each line; returns (audio_path_or_None, spoken_seconds) per scene."""
    result = []
    for i, line in enumerate(lines):
        audio = synthesize(settings, line, workdir / f"voice_{i + 1:02d}.mp3")
        result.append((audio, probe_duration(audio) if audio else 0.0))
    return result
