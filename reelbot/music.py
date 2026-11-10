"""Generate original, royalty-free background music beds (soft piano-like melody over warm pads).

    python -m reelbot.music            # writes assets/music/*.m4a

Each track is ~70 s at a slow tempo, quiet and simple so it sits under the Malayalam voice.
The video assembler picks one at random per reel and mixes it at REELBOT_MUSIC_VOLUME.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 32000
NOTE = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def freq(name: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave - 4)) / 12)


def pluck(f: float, dur: float, amp: float) -> np.ndarray:
    """Soft piano/music-box tone: a few harmonics with fast attack and exponential decay."""
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(t / 0.012, 1.0) * np.exp(-t * 2.6)
    tone = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in ((1, 1.0), (2, 0.35), (3, 0.12), (4, 0.05)))
    return amp * env * tone


def pad(freqs: list[float], dur: float, amp: float) -> np.ndarray:
    """Warm sustained chord: slightly detuned sines with slow swell."""
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(t / 1.2, 1.0) * np.minimum((dur - t) / 1.2, 1.0)
    trem = 1 + 0.06 * np.sin(2 * np.pi * 0.25 * t)
    sig = sum(np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.003 * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t)
              for f in freqs)
    return amp * env * trem * sig / len(freqs)


TRACKS = {
    # name: (bpm, chords as (root names for pad), melody pool per chord)
    "nostalgia_a_minor": (68, [("A", "C", "E"), ("F", "A", "C"), ("C", "E", "G"), ("G", "B", "D")]),
    "warm_d_major": (72, [("D", "F#", "A"), ("B", "D", "F#"), ("G", "B", "D"), ("A", "C#", "E")]),
    "gentle_e_minor": (64, [("E", "G", "B"), ("C", "E", "G"), ("G", "B", "D"), ("D", "F#", "A")]),
}


def make_track(name: str, bpm: int, chords: list[tuple[str, ...]], length: float = 70.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = 4 * beat
    out = np.zeros(int((length + 4) * SR))
    t, i = 0.0, 0
    while t < length:
        chord = chords[i % len(chords)]
        p = pad([freq(n, 3) for n in chord], bar + 1.0, 0.16)
        s = int(t * SR)
        out[s:s + len(p)] += p[: len(out) - s]
        # sparse melody: 3-5 notes per bar from the chord + a passing tone, higher octave
        pool = [freq(n, 5) for n in chord] + [freq(chord[0], 6)]
        for k in range(4):
            if rng.random() < 0.8:
                f = pool[rng.integers(len(pool))]
                note = pluck(f, 2.4, 0.22 if k == 0 else 0.16)
                ns = int((t + k * beat + rng.uniform(0, 0.03)) * SR)
                out[ns:ns + len(note)] += note[: len(out) - ns]
        # soft bass on the root
        b = pluck(freq(chord[0], 2), bar, 0.18)
        out[s:s + len(b)] += b[: len(out) - s]
        t += bar
        i += 1
    out = out[: int(length * SR)]
    fade = int(3 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out /= max(np.max(np.abs(out)), 1e-9) / 0.8
    return out


def write(path: Path, sig: np.ndarray) -> Path:
    wav = path.with_suffix(".wav")
    stereo = np.stack([sig, np.roll(sig, int(0.012 * SR))], axis=1)  # tiny delay = width
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    # light reverb + encode
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-af",
                    "aecho=0.8:0.7:120|240:0.25|0.15,lowpass=f=6500,loudnorm=I=-20:TP=-2",
                    "-c:a", "aac", "-b:a", "96k", str(path)], check=True)
    wav.unlink()
    return path


def main() -> None:
    out_dir = Path("assets/music")
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, (name, (bpm, chords)) in enumerate(TRACKS.items(), 1):
        p = write(out_dir / f"{name}.m4a", make_track(name, bpm, chords, seed=n))
        print(p, round(p.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
