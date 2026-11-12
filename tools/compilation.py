"""Build a 16:9 long-form compilation from finished vertical story reels.

Usage:
  python tools/compilation.py OUT.mp4 "<title in Malayalam>" DIR1 DIR2 ...

Each DIR holds reel.mp4 (rendered without the end card: REELBOT_END_CARD="") plus story.json
and scenes/. The video gets an intro card, a chapter card before each story ("കഥ N" + title),
and an outro card. Reels rendered with REELBOT_LANDSCAPE=1 fill the 16:9 frame; vertical reels are padded with a blurred copy.
Writes OUT.mp4 and OUT.chapters.txt (YouTube chapter timestamps for the description).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

W, H, FPS = 1920, 1080, 30
MUSIC = Path(__file__).resolve().parent.parent / "assets" / "music" / "nostalgia_a_minor.m4a"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def run(cmd):
    subprocess.run(cmd, check=True)


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def ass(lines: list[tuple[str, int, str]], dur: float, path: Path) -> Path:
    """lines: (text, size, colour &HBBGGRR) stacked around the centre."""
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: C,Manjari,80,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,4,3,5,120,120,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    end = f"0:{int(dur // 60):02d}:{dur % 60:05.2f}"
    text = "\\N".join(f"{{\\fs{size}\\c{col}}}{t}" for t, size, col in lines)
    path.write_text(head + f"Dialogue: 0,0:00:00.00,{end},C,,0,0,0,,{{\\fad(400,400)}}{text}\n", encoding="utf-8")
    return path


def card(bg_png: Path, lines, dur: float, out: Path, tmp: Path, music_at: float) -> Path:
    sub = ass(lines, dur, tmp / (out.stem + ".ass"))
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"eq=brightness=-0.38:saturation=0.85,fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4,ass='{sub}'")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{dur}", "-i", str(bg_png),
         "-ss", f"{music_at}", "-t", f"{dur}", "-i", str(MUSIC),
         "-vf", vf, "-af", f"volume=0.35,afade=t=in:d=0.4,afade=t=out:st={dur - 0.5:.2f}:d=0.5",
         "-shortest", *ENC, str(out)])
    return out


def widen(reel: Path, out: Path) -> Path:
    w, h = (int(x) for x in subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(reel)], capture_output=True, text=True, check=True).stdout.split(",")[:2])
    if w > h:  # already rendered widescreen (REELBOT_LANDSCAPE=1): full frame, no padding
        run(["ffmpeg", "-y", "-v", "error", "-i", str(reel), "-vf", f"scale={W}:{H},setsar=1", *ENC, str(out)])
        return out
    fc = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"boxblur=30:5,eq=brightness=-0.18[bg];[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,setsar=1[v]")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(reel), "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
         *ENC, str(out)])
    return out


def main() -> None:
    """Env options: COMP_LABEL (chapter word, default കഥ), COMP_SUBTITLE (intro line 2),
    COMP_PROLOGUE=1 (first dir plays before the title card, without a chapter card),
    COMP_OUTRO1 / COMP_OUTRO2 (closing card lines)."""
    import os
    out, title, dirs = Path(sys.argv[1]), sys.argv[2], [Path(d) for d in sys.argv[3:]]
    label = os.environ.get("COMP_LABEL", "കഥ")
    prologue = dirs.pop(0) if os.environ.get("COMP_PROLOGUE") == "1" else None
    subtitle = os.environ.get("COMP_SUBTITLE", f"{len(dirs)} ഓർമ്മക്കഥകൾ")
    tmp = Path(tempfile.mkdtemp(prefix="comp_"))
    parts, chapters, t = [], [], 0.0
    if prologue:
        p = widen(prologue / "reel.mp4", tmp / "00_prologue.mp4")
        parts.append(p)
        chapters.append("0:00 " + (json.loads((prologue / "story.json").read_text(encoding="utf-8")).get("title_ml") or "Intro"))
        t += duration(p)
    first_bg = sorted((dirs[0] / "scenes").glob("scene_*.png"))[-1]
    intro = card(first_bg, [(title, 140, "&H8AE0FF&"), (subtitle, 90, "&HFFFFFF&")], 4.0, tmp / "00_intro.mp4", tmp, 0)
    if not prologue:
        chapters.append("0:00 Intro")
    parts.append(intro)
    t += duration(intro)
    for i, d in enumerate(dirs, 1):
        story = json.loads((d / "story.json").read_text(encoding="utf-8"))
        name = story.get("title_ml") or d.name
        bg = sorted((d / "scenes").glob("scene_*.png"))[1]
        chapters.append(f"{int(t // 60)}:{int(t % 60):02d} {i}. {name} | {story.get('title_en', '')}".rstrip(" |"))
        c = card(bg, [(f"{label} {i}", 90, "&HFFFFFF&"), (name, 130, "&H8AE0FF&")], 2.6, tmp / f"{i:02d}a.mp4", tmp, 4 + i * 3)
        s = widen(d / "reel.mp4", tmp / f"{i:02d}b.mp4")
        parts += [c, s]
        t += duration(c) + duration(s)
    outro = card(sorted((dirs[-1] / "scenes").glob("scene_*.png"))[-1],
                 [(os.environ.get("COMP_OUTRO1", "ഈ കഥകൾ ഇഷ്ടമായെങ്കിൽ"), 100, "&HFFFFFF&"),
                  (os.environ.get("COMP_OUTRO2", "സബ്സ്ക്രൈബ് ചെയ്യൂ"), 130, "&H8AE0FF&")],
                 5.0, tmp / "99_outro.mp4", tmp, 40)
    parts.append(outro)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(out)])
    out.with_suffix(".chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    print(out, f"{duration(out):.1f}s")


if __name__ == "__main__":
    main()
