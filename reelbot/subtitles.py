"""ASS subtitles. libass (used by ffmpeg) shapes Malayalam conjuncts correctly via HarfBuzz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _ts(seconds: float) -> str:
    cs = int(round(max(seconds, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escape(text: str) -> str:
    text = text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    return "\\N".join(line.strip() for line in text.strip().splitlines() if line.strip())


def build_ass(cues: list[Cue], font: str, width: int = 1080, height: int = 1920) -> str:
    # Bottom-centre, sitting above the area Instagram covers with the caption/buttons.
    style = (
        f"Style: Story,{font},82,&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,6,2,2,80,80,460,1"
    )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = [
        f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},Story,,0,0,0,,{{\\fad(150,150)}}{escape(c.text)}"
        for c in cues
    ]
    return header + "\n".join(events) + "\n"


def write_ass(cues: list[Cue], font: str, out: Path, width: int = 1080, height: int = 1920) -> Path:
    out.write_text(build_ass(cues, font, width, height), encoding="utf-8")
    return out
