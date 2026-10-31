#!/usr/bin/env bash
# Rebuild the demo video from scratch: records every scene from saved answers, then cuts it to the voice-over.
# Put the voice file in this folder as voiceover.mp3 (or .wav/.m4a). Without it you get a silent draft.
# Needs: node + playwright (global), ffmpeg, python deps of the backend. Output: $WORK/quorum-demo.mp4
set -euo pipefail
cd "$(dirname "$0")"
WORK=${WORK:-/tmp/quorum-video}
rm -rf "$WORK"; mkdir -p "$WORK/db"
VOICE=$(ls voiceover.* 2>/dev/null | head -1 || true)
(cd ../frontend && npm ci --silent && VITE_USE_MOCKS=false npm run build --silent)
(cd ../backend && DATABASE_URL=sqlite:///$WORK/db/q.db CHECKPOINT_DB=$WORK/db/c.db EMBEDDINGS_ENABLED=0 DEMO_REPLAY=1 \
  python -m uvicorn app.main:app --port 8001 > "$WORK/server.log" 2>&1) &
trap 'pkill -P $$ || true' EXIT
sleep 9
curl -s -X POST localhost:8001/api/demo/reset > /dev/null
NODE_PATH=$(npm root -g) node record.js http://127.0.0.1:8001 "$WORK/rec"
python3 assemble.py --rec "$WORK/rec" ${VOICE:+--voice "$VOICE"} --out "$WORK/quorum-demo.mp4"
echo "Done: $WORK/quorum-demo.mp4"
