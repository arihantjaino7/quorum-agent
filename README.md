# Quorum: meetings that remember

> Status: scaffold. This README is a stub until the demo build lands.

Quorum is a meeting-to-execution agent. You hold the Wispr Flow key after a meeting and ramble
for 30 seconds. Quorum cleans the speech, pulls out decisions and tasks, **checks them against
everything your team decided before**, shows what each change breaks downstream, asks you to
confirm, and then files the tasks, schedules reminders, and briefs everyone affected.

Built by voice for the Product Space × Wispr Flow Agentic AI Hackathon.

## Repo map
| Path | Owner | What |
|---|---|---|
| `backend/` | Claude Code | FastAPI + LangGraph agents, SQLite memory, integrations |
| `frontend/` | Codex | UI |
| `CONTRACT.md` | Claude Code | API contract, the source of truth between the two |
| `PLAN_BACKEND.md` | Claude Code | Phased backend build plan |

## Run the backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # keys are optional
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/api/health
```

The first memory search downloads the local embedding model (~70MB, cached in `backend/.cache/`).
Do it once before a demo on venue wifi: `cd backend && python -c "from app.services import embeddings; embeddings.embed(['warm up'])"`.

## Tests
```bash
cd backend && pytest
```

Deploying: see [DEPLOY.md](DEPLOY.md) (one Render service, Docker).
