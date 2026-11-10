"""ASS subtitles. libass (used by ffmpeg) shapes Malayalam conjuncts correctly via HarfBuzz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cue:
    start: float
    end: float
    text: str
    style: str = "Story"


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


def _wrap(text: str, line_chars: int = 22) -> str:
    return "\n".join(wrap_chunks(text, line_chars, lines=99))


def build_ass(cues: list[Cue], font: str, width: int = 1080, height: int = 1920) -> str:
    # Bottom-centre, sitting above the area Instagram covers with the caption/buttons.
    style = (
        f"Style: Story,{font},82,&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,6,2,2,80,80,460,1"
    )
    # Hook: big yellow question at the top for the first seconds. End: small subscribe line at the top.
    hook = (
        f"Style: Hook,{font},92,&H0000E6FF,&H0000E6FF,&H00101010,&H96000000,"
        "-1,0,0,0,100,100,0,0,1,7,3,8,70,70,230,1"
    )
    end = (
        f"Style: End,{font},64,&H00FFFFFF,&H00FFFFFF,&H00202020,&H96000000,"
        "-1,0,0,0,100,100,0,0,3,5,0,8,90,90,250,1"
    )
    # Reveal: the twist line, large warm gold in the middle of the frame.
    reveal = (
        f"Style: Reveal,{font},100,&H008AE0FF,&H008AE0FF,&H00101010,&H96000000,"
        "-1,0,0,0,100,100,0,0,1,7,4,2,70,70,380,1"
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
{hook}
{end}
{reveal}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = [
        f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},{c.style},,0,0,0,,{{\\fad(150,150)}}{escape(_wrap(c.text) if c.style in ('Hook', 'Reveal') else c.text)}"
        for c in cues
    ]
    return header + "\n".join(events) + "\n"


def write_ass(cues: list[Cue], font: str, out: Path, width: int = 1080, height: int = 1920) -> Path:
    out.write_text(build_ass(cues, font, width, height), encoding="utf-8")
    return out
