"""Scene boundaries for a narration: estimate from text length, then snap to the longest nearby pause."""
import json, re, subprocess, sys
story, audio, out = sys.argv[1:4]
d = json.load(open(story))
lens = [len((s['narration_ml'] + s.get('dialogue_ml', '')).replace(' ', '')) for s in d['scenes']]
err = subprocess.run(["ffmpeg", "-i", audio, "-af", "silencedetect=n=-35dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True).stderr
st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
sil = list(zip(st, en))
total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio], capture_output=True, text=True).stdout)
speech = total - sum(e - s for s, e in sil)
def t_at(frac):
    target, acc, cur = frac * speech, 0.0, 0.0
    for s, e in sil:
        if acc + (s - cur) >= target:
            return cur + (target - acc)
        acc += s - cur; cur = e
    return cur + (target - acc)
bounds, cum, tot = [], 0, sum(lens)
for L in lens[:-1]:
    cum += L; est = t_at(cum / tot)
    lo = bounds[-1] + 0.8 if bounds else 0.5
    cands = [(s, e) for s, e in sil if lo < (s + e) / 2 and abs((s + e) / 2 - est) < 2.5]
    if not cands:
        cands = [min(((s, e) for s, e in sil if (s + e) / 2 > lo), key=lambda x: abs((x[0] + x[1]) / 2 - est))]
    s, e = max(cands, key=lambda x: (x[1] - x[0]) - 0.15 * abs((x[0] + x[1]) / 2 - est))
    bounds.append((s + e) / 2)
json.dump(bounds, open(out, "w"))
print(" ".join(f"{b:.1f}" for b in bounds), f"/ {total:.1f}")
