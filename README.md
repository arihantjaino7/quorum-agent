# Quorum: meetings that remember

Quorum is a meeting-to-execution agent. After a meeting you talk (with Wispr Flow) and Quorum cleans the speech, pulls out
decisions and tasks, **checks them against everything your team decided before**, shows what each change breaks downstream,
asks you to confirm, and only then files tasks and briefs the people affected.

Built for the Product Space × Wispr Flow Agentic AI Hackathon.

## What it does
- Voice or transcript input (`.txt`, `.vtt`, `.srt`, audio via Groq Whisper)
- Agent pipeline (LangGraph): clean up, extract, recall, cross-check, ripple, human review, execute, remember
- Conflict detection against past decisions, plus deadline-collision and overload warnings
- Ripple effect: reschedules or rescopes work built on a reversed decision, and drafts a heads-up per person
- Spoken edits to the review, decision memory with history, time machine, walk-in brief, change radar
- Ask your meetings (answers quote the meeting), team board, weekly digest per person, reminders
- Notion, GitHub Issues and Telegram integrations; every one is optional and degrades gracefully

## Layout
| Path | What |
|---|---|
| `backend/` | FastAPI + LangGraph agents, SQLite memory, integrations, tests |
| `frontend/` | React + Vite + Tailwind UI |
| `Dockerfile`, `render.yaml` | One image that serves the site and the API |

## Run locally
```bash
# backend (http://localhost:8000/api/health)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env        # every key is optional
uvicorn app.main:app --reload --port 8000

# frontend (http://localhost:5173), in another terminal
cd frontend
npm install
echo "VITE_USE_MOCKS=false" > .env.local
npm run dev
```
Open the site and press "Play the sample debrief". With `DEMO_REPLAY=1` (the default) the sample runs from saved model answers;
anything else goes live to Groq when `GROQ_API_KEY` is set.

## Tests
```bash
cd backend && pytest -q
cd frontend && npm test
```

## Deploy (Render, one Docker service)
1. Push the repo to GitHub. In Render choose **New → Blueprint** and pick the repo; it reads `render.yaml`.
2. Set `GROQ_API_KEY`. Optional: `NOTION_TOKEN` + `NOTION_DATABASE_ID` (properties: Name, Owner, Due, Status, Meeting),
   `GITHUB_TOKEN` + `GITHUB_REPO`, `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
3. Open the service URL; `/api/health` shows which integrations are connected.

The first start seeds the "Pocket" demo project. The free plan has no disk, so data resets on restart; attach a disk at
`/app/backend/data` to keep it. `EMBEDDINGS_ENABLED=0` keeps memory low on the free plan (recall falls back to topic matching).
