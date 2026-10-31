"""Join one recording per narration part into voiceover.wav and write each part's start time (voice_starts.json).

  python join_voice.py <folder-with-the-18-files> <out-folder>
Files are matched by their number: "...Road.m4a" is part 1, "...Road_2.m4a" is part 2, and so on.
Each file is transcribed and compared with its narration part, so a wrong order or a missed line is reported.
"""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
import httpx

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from assemble import parts, norm

GAP = 0.55


def number(p: Path) -> int:
    m = re.search(r"Road_(\d+)\.\w+$", p.name)
    return int(m.group(1)) if m else 1


def say(path: Path) -> str:
    cache = Path(tempfile.gettempdir()) / f"say-{path.stat().st_size}-{path.name[-14:]}.txt"
    if cache.exists():
        return cache.read_text()
    key = os.environ.get("GROQ_API_KEY") or "proxy-injected"
    for attempt in range(8):
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                       data={"model": "whisper-large-v3-turbo", "response_format": "json", "language": "en"},
                       files={"file": (path.name, path.read_bytes())}, timeout=120)
        if r.status_code != 429:
            break
        wait = float(r.headers.get("retry-after", 20)); print(f"  rate limited, waiting {wait:.0f}s"); time.sleep(wait + 1)
    r.raise_for_status()
    cache.write_text(r.json()["text"])
    return r.json()["text"]


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.m4a"), key=number)
    scenes = parts(HERE / "NARRATION.md")
    if len(files) != len(scenes):
        sys.exit(f"{len(files)} audio files but {len(scenes)} narration parts")
    # Match every file to the narration part it actually says (file numbers can be out of order).
    heard = {f: say(f) for f in files}
    def score(f, text):
        want, got = [norm(w) for w in text.split()], {norm(w) for w in heard[f].split()}
        return sum(1 for w in want if w in got) / len(want)
    order = {}
    for f in files:
        best = max(range(len(scenes)), key=lambda k: score(f, scenes[k]))
        order[best] = f
    if sorted(order) != list(range(len(scenes))):
        sys.exit("Could not match each file to a different narration part: " + str({f.name: max(range(len(scenes)), key=lambda k: score(f, scenes[k])) + 1 for f in files}))
    clips, starts, t = [], [], 0.0
    for i in range(len(scenes)):
        f, text = order[i], scenes[i]
        print(f"part {i + 1:>2} <- {f.name[-12:]:>12}: {score(f, text):4.0%} of the words match   {heard[f][:60]!r}")
        wav = out / f"p{i + 1:02d}.wav"
        trim = "silenceremove=start_periods=1:start_threshold=-42dB,areverse,silenceremove=start_periods=1:start_threshold=-42dB,areverse"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(f), "-ac", "1", "-ar", "44100", "-af", trim, str(wav)], check=True)
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
        starts.append(round(t, 3)); clips.append((wav, d)); t += d + GAP
    inputs, filt = [], []
    for k, (wav, _) in enumerate(clips):
        inputs += ["-i", str(wav)]
        filt.append(f"[{k}:a]apad=pad_dur={GAP}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(clips))) + f"concat=n={len(clips)}:v=0:a=1[a]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[a]", str(out / "voiceover.wav")], check=True)
    (out / "voice_starts.json").write_text(json.dumps({"starts": starts, "total": round(t - GAP, 3)}))
    print(f"joined {len(clips)} parts, {t - GAP:.1f}s total")


if __name__ == "__main__":
    main()
