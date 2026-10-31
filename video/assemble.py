"""Cut the screen recording to the narration.

  python assemble.py --out final.mp4 --rec out/ --voice voiceover.mp3     # final, aligned to the voice
  python assemble.py --out draft.mp4 --rec out/                           # silent draft at natural speed

The voice is transcribed with word timestamps; each numbered narration part is found by its first words, and the matching
screen scene is sped up or slowed down (and frozen on its last frame if needed) to fill exactly that stretch of audio.
"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
W, H, FPS = 1920, 1080, 30


def parts(narration: Path) -> list[str]:
    text = narration.read_text()
    found = re.findall(r"\*\*(\d+) · [^*]+\*\*\n(.+?)(?=\n\n\*\*\d+ ·|\Z)", text, flags=re.S)
    return [re.sub(r"\s+", " ", body.strip()) for _, body in found]


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def transcribe(voice: Path) -> list[dict]:
    import httpx
    key = os.environ.get("GROQ_API_KEY") or "proxy-injected"
    with httpx.Client(timeout=180) as c:
        r = c.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                   data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json", "timestamp_granularities[]": ["word", "segment"]},
                   files={"file": (voice.name, voice.read_bytes())})
    r.raise_for_status()
    body = r.json()
    if body.get("words"):
        return body["words"]
    words = []                                          # fall back: spread each segment's words evenly over its span
    for seg in body.get("segments", []):
        toks = seg["text"].split()
        for k, tok in enumerate(toks):
            words.append({"word": tok, "start": seg["start"] + (seg["end"] - seg["start"]) * k / max(1, len(toks))})
    return words


def align(scenes: list[str], words: list[dict]) -> list[float]:
    heard = [norm(w["word"]) for w in words]
    starts, cursor = [], 0
    for i, text in enumerate(scenes):
        anchor = [norm(w) for w in text.split()[:4]]
        best, best_pos = -1, None
        for pos in range(cursor, len(heard) - 1):
            score = sum(1 for k, a in enumerate(anchor) if pos + k < len(heard) and heard[pos + k] == a)
            if score > best:
                best, best_pos = score, pos
            if score == len(anchor):
                break
        if best_pos is None or best < 2:
            sys.exit(f"Could not find narration part {i + 1} in the audio (best match {best}/{len(anchor)}). Starts with: {' '.join(anchor)}")
        starts.append(max(0.0, words[best_pos]["start"] - 0.12))
        cursor = best_pos + 1
        print(f"part {i + 1:>2} starts at {starts[-1]:6.2f}s  (matched {best}/{len(anchor)})")
    starts[0] = 0.0
    return starts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", required=True, help="folder with marks.json and the recorded .webm")
    ap.add_argument("--voice")
    ap.add_argument("--out", required=True)
    ap.add_argument("--narration", default=str(HERE / "NARRATION.md"))
    a = ap.parse_args()

    rec = Path(a.rec)
    meta = json.loads((rec / "marks.json").read_text())
    marks = [m["t"] for m in meta["marks"]]            # scene 1..18 starts, then the end
    raw = [marks[i + 1] - marks[i] for i in range(len(marks) - 1)]
    scenes = parts(Path(a.narration))
    if len(scenes) != len(raw):
        sys.exit(f"{len(scenes)} narration parts but {len(raw)} recorded scenes")

    if a.voice:
        voice = Path(a.voice)
        words = transcribe(voice)
        starts = align(scenes, words)
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(voice)]))
        total = duration + 1.0
        targets = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)] + [total - starts[-1]]
    else:
        targets = raw[:]
        total = sum(targets)

    chains, labels = [], []
    n = len(raw)
    chains.append(f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)))
    for i in range(n):
        d, t = raw[i], targets[i]
        f = min(1.7, max(0.2, t / d))                  # >1 slows the scene down, <1 speeds it up
        pad = max(0.0, t - d * f)
        chains.append(f"[s{i}]trim=start={marks[i]:.3f}:end={marks[i + 1]:.3f},setpts=(PTS-STARTPTS)*{f:.4f},fps={FPS},"
                      f"scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration={pad:.3f},trim=duration={t:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
        print(f"scene {i + 1:>2}: recorded {d:5.1f}s -> {t:5.1f}s  (x{f:.2f}{', +%.1fs hold' % pad if pad > 0.05 else ''})")
    chains.append("".join(labels) + f"concat=n={n}:v=1:a=0,fade=t=in:d=0.4,fade=t=out:st={total - 0.6:.2f}:d=0.6[v]")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(rec / meta["video"])]
    if a.voice:
        cmd += ["-i", a.voice]
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]"]
    if a.voice:
        cmd += ["-map", "1:a", "-af", f"loudnorm=I=-16:TP=-1.5,apad,afade=t=in:d=0.2,afade=t=out:st={total - 0.8:.2f}:d=0.8", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-t", f"{total:.2f}", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print("wrote", a.out, f"({total:.1f}s)")


if __name__ == "__main__":
    main()
