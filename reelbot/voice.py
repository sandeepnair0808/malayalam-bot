"""Malayalam voice-over with simple voice casting.

Each scene has a narrator line (`narration_ml`) and optionally a line of dialogue
(`dialogue_ml`) spoken by an on-screen character (`speaker`). Every character gets a
voice preset (man, woman, old man, old woman, boy, girl) built from the two Malayalam
neural voices by adjusting pitch and speed, so the narrator, grandfather and child sound
different.

Providers:
- edge: Microsoft Edge neural voices via `edge-tts` (ml-IN-MidhunNeural / ml-IN-SobhanaNeural). Free.
- gtts: Google Translate TTS via `gTTS` (lang="ml"). Free, one voice only, more robotic.
- none: no narration; scenes get a fixed reading duration from the subtitle length.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

MALE, FEMALE = "ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"


@dataclass(frozen=True)
class VoicePreset:
    voice: str
    pitch: int  # Hz offset
    rate: int  # percent offset


PRESETS = {
    "man": VoicePreset(MALE, 0, 6),
    "woman": VoicePreset(FEMALE, 0, 6),
    "old_man": VoicePreset(MALE, -8, -2),
    "old_woman": VoicePreset(FEMALE, -10, -2),
    "boy": VoicePreset(FEMALE, 28, 10),
    "girl": VoicePreset(FEMALE, 40, 12),
}

GAP = 0.18  # silence between narration and dialogue in one scene

# Gentle "radio warmth": cut rumble, a little body and presence, even out levels, tiny room.
VOICE_POLISH = (
    "highpass=f=75,"
    "equalizer=f=180:t=q:w=1.0:g=2,"
    "equalizer=f=3200:t=q:w=1.2:g=2.5,"
    "equalizer=f=7500:t=q:w=1.5:g=-1.5,"
    "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=150:makeup=2,"
    "aecho=0.85:0.6:35|70:0.10|0.05"
)


def preset_for(kind: str | None, settings: Settings) -> VoicePreset:
    if kind in PRESETS:
        return PRESETS[kind]
    # plain voice name from settings (e.g. REELBOT_VOICE) for anything uncast
    return VoicePreset(settings.voice, 0, 6)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def reading_time(text: str) -> float:
    """Seconds a viewer needs to read a Malayalam subtitle without narration."""
    return max(2.0, min(5.0, 1.0 + len(text) * 0.07))


def settings_rate() -> int:
    """Global speed offset in percent (REELBOT_RATE, e.g. 10 = faster, -10 = slower)."""
    try:
        return int(os.environ.get("REELBOT_RATE", "0"))
    except ValueError:
        return 0


async def _edge(text: str, preset: VoicePreset, rate_extra: int, out: Path) -> None:
    import edge_tts

    # edge-tts uses aiohttp, which ignores proxy env vars unless told explicitly.
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    rate = preset.rate + rate_extra + settings_rate()
    await edge_tts.Communicate(
        text, preset.voice, rate=f"{rate:+d}%", pitch=f"{preset.pitch:+d}Hz", proxy=proxy
    ).save(str(out))


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="ml", slow=False).save(str(out))


def _polish(raw: Path, out: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", VOICE_POLISH, "-ar", "44100", "-ac", "2", str(out)],
        check=True,
    )
    return out


def synthesize(settings: Settings, text: str, out: Path, preset: VoicePreset | None = None,
               rate_extra: int = 0) -> Path | None:
    """Write one polished line of speech (wav). Returns None when narration is disabled or text is empty."""
    provider = settings.tts.lower()
    if provider == "none" or not text.strip():
        return None
    # "..." makes the neural voice stop for a long beat; a comma pause keeps the pace up
    text = re.sub(r"\s*(\.\.\.|…)\s*", ", ", text).strip(" ,")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw.mp3")
    preset = preset or preset_for(None, settings)
    done = False
    if provider == "edge":
        try:
            asyncio.run(_edge(text, preset, rate_extra, raw))
            done = True
        except Exception as err:
            log.warning("edge-tts failed (%s); falling back to gTTS", err)
    if not done:
        _gtts(text, raw)
    return _polish(raw, out.with_suffix(".wav"))


@dataclass
class SceneVoice:
    audio: Path | None  # narration (+ dialogue) for the scene
    duration: float  # seconds of speech
    talk_audio: Path | None  # the part the on-screen speaker says (drives lip-sync)
    talk_offset: float  # where talk_audio starts inside `audio`


def _concat(parts: list[Path], out: Path) -> Path:
    inputs, labels = [], []
    filt = []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        if i < len(parts) - 1:
            filt.append(f"[{i}:a]apad=pad_dur={GAP}[p{i}]")
            labels.append(f"[p{i}]")
        else:
            labels.append(f"[{i}:a]")
    filt.append(f"{''.join(labels)}concat=n={len(parts)}:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    str(out)], check=True)
    return out


def narrate_story(settings: Settings, story, workdir: Path) -> list[SceneVoice]:
    """Voice every scene with the narrator's and characters' presets."""
    cast = {c.id: c.voice for c in story.characters}
    narrator = preset_for(story.narrator_voice, settings)
    result: list[SceneVoice] = []
    last = len(story.scenes) - 1
    for i, scene in enumerate(story.scenes):
        slow = -3 if i == last else 0  # land the final line a touch slower
        n_path = synthesize(settings, scene.narration_ml, workdir / f"narr_{i + 1:02d}.wav", narrator, slow)
        d_path = None
        if scene.dialogue_ml.strip():
            who = preset_for(cast.get(scene.speaker or ""), settings) if scene.speaker else narrator
            d_path = synthesize(settings, scene.dialogue_ml, workdir / f"dlg_{i + 1:02d}.wav", who, slow)
        parts = [p for p in (n_path, d_path) if p]
        if not parts:
            result.append(SceneVoice(None, 0.0, None, 0.0))
            continue
        audio = parts[0] if len(parts) == 1 else _concat(parts, workdir / f"voice_{i + 1:02d}.wav")
        talk_audio, talk_offset = None, 0.0
        if scene.speaker:
            if d_path:
                talk_audio = d_path
                talk_offset = (probe_duration(n_path) + GAP) if n_path else 0.0
            elif n_path:  # older stories: whole line is the speaker's
                talk_audio = n_path
        result.append(SceneVoice(audio, probe_duration(audio), talk_audio, talk_offset))
    return result
