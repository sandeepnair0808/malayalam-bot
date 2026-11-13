"""Render a reel from a chapter WAV voiced line by line (phone/sarvam_voice.py output).

    python tools/line_build.py REEL_DIR CHAPTER.wav LINES.json CHAPTER_NAME

The WAV holds one line per scene narration (and one per dialogue), separated by ~1.5 s of silence.
It is split on those gaps; each scene gets narration + a short pause + its dialogue, and the
speaking character's mouth moves only during the dialogue.
"""
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reelbot.config import Settings
from reelbot.pipeline import load_story, compile_art, render
from reelbot.voice import SceneVoice, probe_duration

PAUSE = 0.35  # between narration and dialogue inside one scene


def split_points(wav: Path, want: int) -> list[tuple[float, float]]:
    """(start, end) of each spoken line, found from the long silent gaps."""
    total = probe_duration(wav)
    for min_gap in (1.2, 1.0, 0.8):
        log = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=n=-45dB:d={min_gap}",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
        gaps = [(s, e) for s, e in zip(starts, ends) if s > 0.05 and e < total - 0.05]
        if len(gaps) == want - 1:
            edges = [0.0] + [x for g in gaps for x in g] + [total]
            return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
    raise SystemExit(f"{wav.name}: found {len(gaps) + 1} lines, expected {want}")


def cut(src: Path, a: float, b: float, dst: Path) -> Path:
    trim = "silenceremove=start_periods=1:start_threshold=-45dB"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
                    "-af", f"{trim},areverse,{trim},areverse", "-ar", "44100", "-ac", "2", str(dst)], check=True)
    return dst


def main() -> None:
    reel, wav, lines_json, name = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    data = json.loads(lines_json.read_text(encoding="utf-8"))
    lines = data[name]["lines"] if isinstance(data, dict) else next(c["lines"] for c in data if c["chapter"] == name)
    spans = split_points(wav, len(lines))
    st = Settings(); story = load_story(reel); compile_art(story, reel / "scenes")
    images = sorted((reel / "scenes").glob("scene_*.png"))
    work = reel / "work"; work.mkdir(exist_ok=True)
    silence = work / "pause.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(PAUSE),
                    str(silence)], check=True)
    k, voices = 0, []
    for i, sc in enumerate(story.scenes, 1):
        parts = []
        if sc.narration_ml.strip():
            parts.append(cut(wav, *spans[k], work / f"ln_{i:02d}_n.wav")); k += 1
        talk, off = None, 0.0
        if sc.speaker and sc.dialogue_ml.strip():
            d = cut(wav, *spans[k], work / f"ln_{i:02d}_d.wav"); k += 1
            off = sum(probe_duration(p) for p in parts) + (PAUSE if parts else 0)
            parts += ([silence] if parts else []) + [d]
            talk = d
        seg = work / f"ln_{i:02d}.wav"
        lst = work / "cat.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), str(seg)], check=True)
        voices.append(SceneVoice(seg, probe_duration(seg), talk, off, 0.0))
    if k != len(lines):
        raise SystemExit(f"used {k} of {len(lines)} lines: scenes and lines do not match")
    print(render(st, story, reel, images, voices))


if __name__ == "__main__":
    main()
