# Deploying Quorum on Render

One Docker service serves the website and the API on the same address, so there is nothing to wire together.

## Steps
1. Push this repo to GitHub (the branch you want live).
2. In Render: **New → Blueprint**, pick the repo and branch. Render reads `render.yaml` and builds the `Dockerfile`.
3. When asked for the secret values, set at least `GROQ_API_KEY`. The rest are optional:
   - `NOTION_TOKEN` + `NOTION_DATABASE_ID` (database properties: Name, Owner, Due, Status, Meeting)
   - `GITHUB_TOKEN` + `GITHUB_REPO` (`owner/name`)
   - `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
4. Open the service URL. `/api/health` shows which integrations are connected.

## Behaviour to know
- The first start seeds the "Pocket" project from meeting 1, so conflicts have memory to hit. **Reset** (the arrow in the top bar) wipes and reseeds.
- The free plan has no disk: data resets on every restart and after idle spin-down. That suits a demo; to keep data, attach a disk at `/app/backend/data`.
- The free plan sleeps after ~15 minutes idle; the first request wakes it (about a minute). Open the page before you present.
- `DEMO_REPLAY=1` replays saved answers for the sample debrief, so the demo never depends on Groq being up. Any other text, uploads and spoken edits call Groq live.
- `EMBEDDINGS_ENABLED=0` keeps memory under the free plan's 512 MB. Recall then matches by topic only, which is enough for the sample demo. Set it to `1` on a bigger plan.
- Everything is public once deployed. Anyone with the link can run the demo.

## Run the same image locally
```bash
docker build -t quorum .
docker run -p 8000:8000 -e GROQ_API_KEY=... quorum
```
