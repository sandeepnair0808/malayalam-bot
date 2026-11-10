"""ASS subtitles. libass (used by ffmpeg) shapes Malayalam conjuncts correctly via HarfBuzz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cue:
    start: float
    end: float
    text: str


def wrap_chunks(text: str, line_chars: int = 28, lines: int = 2) -> list[str]:
    """Split spoken text into on-screen chunks of at most `lines` lines of ~`line_chars` characters."""
    words = text.replace("\n", " ").split()
    out_lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > line_chars:
            out_lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out_lines.append(cur)
    return ["\n".join(out_lines[i:i + lines]) for i in range(0, len(out_lines), lines)]


def timed_chunks(text: str, start: float, end: float, quote: bool = False) -> list[tuple[str, float, float]]:
    """Spread the chunks of `text` over [start, end] in proportion to their length."""
    chunks = wrap_chunks(text)
    if not chunks:
        return []
    if quote:
        chunks[0] = "\"" + chunks[0]
        chunks[-1] = chunks[-1] + "\""
    total = sum(len(c) for c in chunks)
    out, t = [], start
    for c in chunks:
        dt = (end - start) * len(c) / total
        out.append((c, t, t + dt))
        t += dt
    return out


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
