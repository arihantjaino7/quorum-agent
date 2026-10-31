"""Record the replay answers for the seed inputs by running them through the real pipeline.

    cd backend && python -m scripts.record_seed [debrief2] [debrief_agree]
    QUORUM_RECORD_ONLY=conflict_detector python -m scripts.record_seed   # re-record just one agent

Inputs: debrief2 (the stage demo, 3 conflicts) and debrief_agree (negative case, 0 conflicts). Default: both.

Uses a throwaway database, calls Groq live for every implemented agent, and saves recordings to
app/replay/recordings/. Prints the resulting review so you can eyeball it before committing.
Re-run after changing a prompt or schema (the old recording no longer matches and the golden test says so).
"""

import json
import os
import sys
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="quorum-record-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{tmp / 'rec.db'}",
    "CHECKPOINT_DB": str(tmp / "ckpt.db"),
    "QUORUM_RECORD": "1",
    "DEMO_REPLAY": "1",
    "REPLAY_STEP_MS": "0",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.config import BACKEND_DIR  # noqa: E402
from app.main import app  # noqa: E402

SEED = BACKEND_DIR / "seed"


INPUTS = {
    "debrief2": {"title": "Investor sync debrief", "date": "2026-10-31"},
    "debrief_agree": {"title": "Standup update", "date": "2026-10-31"},
}


def record(c: TestClient, name: str) -> int:
    meta = {"project": "Pocket", "speaker": "Priya", "source_type": "voice", **INPUTS[name]}
    print(f"\n=== {name}")
    c.post("/api/demo/reset")
    tid = c.post("/api/ingest", json={**meta, "text": (SEED / f"{name}.txt").read_text()}).json()["thread_id"]
    review = None
    with c.stream("GET", f"/api/runs/{tid}/stream") as s:
        for line in s.iter_lines():
            if not line.startswith("data:"):
                continue
            e = json.loads(line[5:])
            print(f"  {e['type']:14} {e['agent']:18} {e['message']}")
            if e["type"] == "error":
                return 1
            if e["type"] == "review_ready":
                review = e["payload"]
                break
    if review is None:
        return 1
    print("\nCORRECTIONS")
    for x in review["corrections"]:
        print(f"  [{x['kind']}] {x['original']!r} → {x['resolved']!r}")
    print("\nCLEAN TEXT\n  " + review["clean_text"])
    print("\nDECISIONS")
    for d in review["decisions"]:
        print(f"  {d['topic_key']}: {d['statement']}  (made_by {d['made_by']})\n      quote: {d['source_quote']!r}")
    print("\nTASKS")
    for t in review["tasks"]:
        print(f"  {t['owner']}: {t['title']}  due {t['due_date']} ({t['raw_due_phrase']!r})\n      quote: {t['source_quote']!r}")
    print("\nQUESTIONS", review["questions"])
    print("\nCONFLICTS")
    for x in review["conflicts"]:
        old = (x["old_decision"] or {}).get("statement")
        print(f"  [{x['severity']}] {x['type']}: {old!r} → {x['explanation']}\n      affected: "
              f"{[t['title'] for t in x['affected_tasks']]}\n      resolve: {x['suggested_resolution']}")
    return 0


def main() -> int:
    names = sys.argv[1:] or list(INPUTS)
    with TestClient(app) as c:
        for name in names:
            if record(c, name):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
