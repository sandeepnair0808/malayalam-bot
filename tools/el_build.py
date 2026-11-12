"""Build a reel from one pre-recorded narration file split at given scene boundaries."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/home/user/malayalam-bot")
from reelbot.config import Settings
from reelbot.pipeline import load_story, compile_art, render
from reelbot.voice import SceneVoice, probe_duration

reel, audio, bounds = Path(sys.argv[1]), sys.argv[2], json.load(open(sys.argv[3]))
st = Settings(); story = load_story(reel); compile_art(story, reel / "scenes")
images = sorted((reel / "scenes").glob("scene_*.png"))
work = reel / "work"; work.mkdir(exist_ok=True)
total = probe_duration(Path(audio)); edges = [0.0] + bounds + [total]
voices = []
for i, sc in enumerate(story.scenes):
    a, b = edges[i], edges[i + 1]
    seg = work / f"el_{i + 1:02d}.wav"
    # trim leading/trailing silence of the segment so scene timing follows the words
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", audio,
                    "-af", "silenceremove=start_periods=1:start_threshold=-40dB,areverse,silenceremove=start_periods=1:start_threshold=-40dB,areverse",
                    "-ar", "44100", "-ac", "2", str(seg)], check=True)
    dur = probe_duration(seg)
    narr, dlg = sc.narration_ml.strip(), sc.dialogue_ml.strip()
    talk, off = None, 0.0
    if sc.speaker and dlg:
        off = dur * len(narr) / max(len(narr) + len(dlg), 1)
        talk = work / f"el_talk_{i + 1:02d}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{off:.3f}", "-i", str(seg), str(talk)], check=True)
    elif sc.speaker:
        talk = seg
    voices.append(SceneVoice(seg, dur, talk, off, 0.0))
print(render(st, story, reel, images, voices))
