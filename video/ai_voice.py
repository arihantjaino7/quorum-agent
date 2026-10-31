"""Speak the narration with a local neural voice (Kokoro) and write voiceover.wav + voice_starts.json.

  python ai_voice.py <model-folder> <out-folder> [voice] [speed]
Model files (kokoro-v1.0.onnx, voices-v1.0.bin) come from the kokoro-onnx release.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from assemble import parts

GAP = 0.6
SAY = {"Wispr Flow": "Wisper Flow", "V-T-T": "V T T", "S-R-T": "S R T"}   # pronunciation hints for the speech engine only


def main() -> None:
    model, out = Path(sys.argv[1]), Path(sys.argv[2])
    voice = sys.argv[3] if len(sys.argv) > 3 else "af_heart"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    out.mkdir(parents=True, exist_ok=True)
    tts = Kokoro(str(model / "kokoro-v1.0.onnx"), str(model / "voices-v1.0.bin"))
    sr, pieces, starts, t = 24000, [], [], 0.0
    gap = np.zeros(int(GAP * sr), dtype=np.float32)
    for i, text in enumerate(parts(HERE / "NARRATION.md"), 1):
        for a, b in SAY.items():
            text = text.replace(a, b)
        samples, rate = tts.create(text, voice=voice, speed=speed, lang="en-us")
        assert rate == sr
        samples = samples.astype(np.float32)
        starts.append(round(t, 3)); pieces += [samples, gap]; t += len(samples) / sr + GAP
        print(f"part {i:>2}: {len(samples) / sr:5.1f}s")
    audio = np.concatenate(pieces[:-1])
    sf.write(out / "voiceover.wav", audio, sr)
    (out / "voice_starts.json").write_text(json.dumps({"starts": starts, "total": round(t - GAP, 3)}))
    print(f"total {t - GAP:.1f}s with voice {voice}")


if __name__ == "__main__":
    main()
