"""Record the replay answers for the seed demo (debrief2) by running it through the real pipeline.

    cd backend && python -m scripts.record_seed

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


def main() -> int:
    exp = json.loads((SEED / "expected_debrief2.json").read_text())
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        tid = c.post("/api/ingest", json={**exp["meeting"], "text": (SEED / "debrief2.txt").read_text()}).json()["thread_id"]
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
