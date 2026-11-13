"""Re-render Shorts with Sarvam audio from the phone (python sarvam_voice.py --next N).

    python tools/sarvam_shorts.py OUT_DIR WAV1 WAV2 ...      # WAV named <story-slug>.wav

For each story: rebuilds the story dir from its pack, renders with tools/line_build.py and prints
"DONE <slug> <reel.mp4>". Copy the reels to the reels branch at their uploads.json path.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from reelbot.pipeline import save_story
from reelbot.storypack import parse

out = Path(sys.argv[1])
lines = json.loads((ROOT / "stories" / "shorts_lines.json").read_text(encoding="utf-8"))
for wav in map(Path, sys.argv[2:]):
    slug = wav.stem
    d = out / slug
    if (d / "reel.mp4").exists():
        print("DONE", slug, d / "reel.mp4", flush=True)
        continue
    story = dict(parse((ROOT / lines[slug]["pack"]).read_text(encoding="utf-8")))[slug]
    (d / "scenes").mkdir(parents=True, exist_ok=True)
    save_story(story, d)
    with open(out / f"{slug}.log", "w") as log:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_build.py"), str(d), str(wav),
                            str(ROOT / "stories" / "shorts_lines.json"), slug],
                           stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    print(("DONE" if r.returncode == 0 else "FAIL"), slug, d / "reel.mp4", flush=True)
    subprocess.run(["rm", "-rf", str(d / "work")])
print("ALLDONE", flush=True)
