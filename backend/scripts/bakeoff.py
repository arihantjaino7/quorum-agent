"""Model bake-off on the seed debrief: which Groq models should play the strong and fast roles?

Each candidate runs the draft normalizer prompt and the draft extractor prompt on debrief2.txt, several
times, scored against seed/expected_debrief2.json. Calls go straight to Groq (no replay, nothing recorded).
Paced for the free tier: when Groq asks for a wait longer than the app's budget, the script waits it out and
reruns that run. Times are the model's own answer time, excluding rate-limit waits.

    cd backend && python -m scripts.bakeoff [--runs 3] [--contenders "model@effort,model"]
"""

import argparse
import asyncio
import json
import re
import statistics
import time
from pathlib import Path

from app.agents import extractor, normalizer
from app.config import BACKEND_DIR
from app.integrations import llm

SEED = BACKEND_DIR / "seed"
DEFAULT_CONTENDERS = ["openai/gpt-oss-120b", "openai/gpt-oss-120b@low", "openai/gpt-oss-20b",
                      "openai/gpt-oss-20b@low", "qwen/qwen3.8-27b"]
_RETRY = re.compile(r"try again in (\d+)s")
_timing: dict = {}


def _timed_complete(original):
    async def wrapper(model, schema, messages, reasoning=None):
        t0 = time.perf_counter()
        out = await original(model, schema, messages, reasoning)
        _timing["last"] = time.perf_counter() - t0
        return out

    return wrapper
RESULTS = Path(__file__).resolve().parent / "bakeoff_results.md"


def score_normalizer(out: normalizer.NormalizerOut, exp: dict) -> tuple[int, int, list[str]]:
    misses, pts = [], 0
    for c in exp["corrections_must_include"]:
        hits = [x for x in out.corrections if x.kind == c["kind"] and c["original_contains"].lower() in x.original.lower()]
        if "resolved_contains" in c:
            hits = [x for x in hits if c["resolved_contains"] in x.resolved]
        if "resolved_date" in c:
            hits = [x for x in hits if c["resolved_date"] in x.resolved]
        pts += bool(hits)
        if not hits:
            misses.append(f"correction {c['kind']}:{c['original_contains']}")
    clean = out.clean_text.lower()
    for w in exp["clean_text_must_not_contain"]:
        pts += w not in clean
        if w in clean:
            misses.append(f"left '{w}' in clean text")
    for keep in ["android", "stripe", "play store", "investor update"]:  # over-deletion guard
        pts += keep in clean
        if keep not in clean:
            misses.append(f"dropped '{keep}'")
    return pts, 4 + len(exp["clean_text_must_not_contain"]) + 4, misses


def score_extractor(out: extractor.ExtractorOut, exp: dict) -> tuple[int, int, list[str]]:
    misses, pts = [], 0
    by_topic = {d.topic_key: d for d in out.decisions}
    for topic, e in exp["decisions_topics"].items():
        d = by_topic.get(topic)
        ok = d is not None and e["statement_contains"].lower() in d.statement.lower()
        pts += ok
        if not ok:
            misses.append(f"decision {topic}")
        if "made_by" in e:
            ok = d is not None and d.made_by == e["made_by"]
            pts += ok
            if not ok:
                misses.append(f"{topic} made_by={d.made_by if d else None}")
    for t in exp["tasks"]:
        hits = [x for x in out.tasks if x.owner == t["owner"] and t["title_contains"].lower() in x.title.lower()]
        x = hits[0] if hits else None
        checks = [x is not None, bool(x and x.due_date == t["due_date"]),
                  bool(x and t["raw_due_phrase_contains"].lower() in x.raw_due_phrase.lower())]
        pts += sum(checks)
        for name, ok in zip(["found", "due", "raw phrase"], checks):
            if not ok:
                misses.append(f"task {t['owner']}/{t['title_contains']}: {name}" + (f" ({x.due_date})" if name == "due" and x else ""))
    extra_d = max(0, len(out.decisions) - len(exp["decisions_topics"]))
    extra_t = max(0, len(out.tasks) - len(exp["tasks"]))
    if extra_d or extra_t:
        misses.append(f"extras: {extra_d} decisions, {extra_t} tasks")
    return pts, len(exp["decisions_topics"]) + 1 + 3 * len(exp["tasks"]), misses


async def one(role: str, contender: str, raw: str, exp: dict) -> dict:
    model, _, effort = contender.partition("@")
    meeting = exp["meeting"]
    if role == "normalizer":
        schema, msgs, scorer = normalizer.NormalizerOut, normalizer.build_messages(raw, meeting["date"], meeting["speaker"]), score_normalizer
    else:
        m1 = json.loads((SEED / "meeting1.json").read_text())
        existing = [(d["topic_key"], d["statement"]) for d in m1["decisions"]]
        schema, scorer = extractor.ExtractorOut, score_extractor
        msgs = extractor.build_messages(raw, meeting["date"], meeting["speaker"], ["Priya", "Rahul", "Ananya"], existing)
    waited = 0.0
    for _ in range(5):
        t0 = time.perf_counter()
        _timing.pop("last", None)
        try:
            out = await llm._live(role, model, schema, msgs, effort or None)
        except Exception as e:  # noqa: BLE001
            m = _RETRY.search(str(e))
            if "rate limit" in str(e) and m:  # longer than the app's budget: wait it out, rerun this run
                secs = int(m.group(1)) + 2
                print(f"    rate limited, pausing {secs}s")
                waited += secs
                await asyncio.sleep(secs)
                continue
            msg = str(e).split(" - {")[0][:160]
            return {"ok": False, "secs": 0.0, "pts": 0, "max": None, "misses": [f"FAILED: {msg}"], "waited": waited}
        waited += max(0.0, time.perf_counter() - t0 - _timing.get("last", 0.0))
        pts, mx, misses = scorer(out, exp)
        return {"ok": True, "secs": _timing.get("last", 0.0), "pts": pts, "max": mx, "misses": misses, "waited": waited}
    return {"ok": False, "secs": 0.0, "pts": 0, "max": None, "misses": ["FAILED: still rate limited"], "waited": waited}


async def main(contenders: list[str], runs: int) -> None:
    llm._complete = _timed_complete(llm._complete)
    raw = (SEED / "debrief2.txt").read_text()
    exp = json.loads((SEED / "expected_debrief2.json").read_text())
    rows = []
    for role in ["normalizer", "extractor"]:
        for model in contenders:
            results = [await one(role, model, raw, exp) for _ in range(runs)]
            mx = next((r["max"] for r in results if r["max"]), 0)
            scores = [r["pts"] for r in results]
            misses = sorted({m for r in results for m in r["misses"]})
            ok_secs = [r["secs"] for r in results if r["ok"]] or [0.0]
            rows.append((role, model, statistics.mean(scores), min(scores), mx, statistics.mean(ok_secs),
                         sum(not r["ok"] for r in results), misses, sum(r["waited"] for r in results)))
            print(f"{role:10} {model:28} avg {statistics.mean(scores):.1f}/{mx}  min {min(scores)}  "
                  f"{statistics.mean(ok_secs):.1f}s  fails {rows[-1][6]}  waited {rows[-1][8]:.0f}s", flush=True)
    lines = [
        "# Model bake-off: debrief2",
        "",
        f"{runs} runs per model and role, temperature 0, draft prompts, scored against `seed/expected_debrief2.json`.",
        "Normalizer: corrections found + digression removed + key content kept. Extractor: decisions, Rahul attribution,",
        "tasks (found, ISO due date, raw phrase). The extractor is given the raw debrief, not the normalizer's output.",
        "",
        "`model@low` = reasoning effort low. Rate-limit waits (free tier) are excluded from the time column.",
        "",
        "| Role | Model | Avg score | Worst run | Avg time | Failed runs | Rate-limit waits | What it missed (any run) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for role, model, avg, worst, mx, secs, fails, misses, waited in rows:
        lines.append(f"| {role} | `{model}` | {avg:.1f}/{mx} | {worst}/{mx} | {secs:.1f}s | {fails} | {waited:.0f}s | "
                     f"{'; '.join(misses) or 'nothing'} |")
    RESULTS.write_text("\n".join(lines) + "\n")
    print(f"\nwritten to {RESULTS}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--contenders", default=",".join(DEFAULT_CONTENDERS))
    a = ap.parse_args()
    asyncio.run(main(a.contenders.split(","), a.runs))
