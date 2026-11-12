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
    # (size, margin_v) per style: 9:16 Shorts keep text above Instagram's caption area; 16:9 sits low like film subtitles
    wide = width > height
    sz = {"Story": (62, 60), "Hook": (78, 50), "End": (50, 40), "Reveal": (80, 110)} if wide else \
         {"Story": (82, 460), "Hook": (92, 230), "End": (64, 250), "Reveal": (100, 380)}
    side = 160 if wide else 80
    # Bottom-centre story text.
    style = (
        f"Style: Story,{font},{sz['Story'][0]},&H00FFFFFF,&H00FFFFFF,&H00202020,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,6,2,2,{side},{side},{sz['Story'][1]},1"
    )
    # Hook: big yellow question at the top for the first seconds. End: small subscribe line at the top.
    hook = (
        f"Style: Hook,{font},{sz['Hook'][0]},&H0000E6FF,&H0000E6FF,&H00101010,&H96000000,"
        f"-1,0,0,0,100,100,0,0,1,7,3,8,{side},{side},{sz['Hook'][1]},1"
    )
    end = (
        f"Style: End,{font},{sz['End'][0]},&H00FFFFFF,&H00FFFFFF,&H00202020,&H96000000,"
        f"-1,0,0,0,100,100,0,0,3,5,0,8,90,90,{sz['End'][1]},1"
    )
    # Reveal: the twist line, large warm gold, low in the frame.
    reveal = (
        f"Style: Reveal,{font},{sz['Reveal'][0]},&H008AE0FF,&H008AE0FF,&H00101010,&H96000000,"
        f"-1,0,0,0,100,100,0,0,1,7,4,2,{side},{side},{sz['Reveal'][1]},1"
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
        f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},{c.style},,0,0,0,,{{\\fad(150,150)}}{escape(_wrap(c.text, 36 if wide else 22) if c.style in ('Hook', 'Reveal') else c.text)}"
        for c in cues
    ]
    return header + "\n".join(events) + "\n"


def write_ass(cues: list[Cue], font: str, out: Path, width: int = 1080, height: int = 1920) -> Path:
    out.write_text(build_ass(cues, font, width, height), encoding="utf-8")
    return out
