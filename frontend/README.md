# Quorum frontend

A voice-first meeting-to-execution prototype, inspired by the user's Rekora design reference. Source lives entirely in `/frontend`. Backend and repository root contract remain owned by the backend agent.

## Run

```powershell
cd frontend
npm ci
npm run dev
```

Open the Vite Local URL (normally `http://127.0.0.1:5173`). Development uses the scripted Pocket demo by default. The mock state persists in this browser. **More workspace actions → Reset demo workspace** restores the original meeting and demo clock.

## Connect the backend

Create `frontend/.env.local`:

```dotenv
VITE_USE_MOCKS=false
```

Restart Vite. `/api` proxies to `http://localhost:8000`. Production builds default to the real API and need the same-origin `/api` reverse proxy; use `npm run build -- --mode development` only when deliberately building a mock preview. Never put API keys into Vite environment variables.

API types and clients match the repository's **CONTRACT.md v1.2** fetched on 31 October 2026. A read-only snapshot with its upstream blob SHA is in `docs/API_CONTRACT_SNAPSHOT.md`. Changes from the initial brief include object-shaped project/people lists, extended SSE metadata and agent names, decision rationale/source quotes, ripples/heads-up approval fields, health, brief, snapshots, timeline and radar endpoints. Root CONTRACT.md wins if it changes.

## Demo in two minutes

1. Capture → **Try the demo** → **Turn this into action**.
2. Watch Normalizer → Extractor → Memory → Conflict check → Ripple effect → your review.
3. Inspect the three conflicts. Choose **Accept all new decisions** or resolve each one.
4. Say/type **Drop the investor update**, then apply the edit. Alternatively assign its owner and deadline in its card.
5. Review the ripple choices, then **Approve & send**.
6. Visit Board and Memory. Ask **Why did we drop Razorpay?** after approval for a cited answer from the new meeting.
7. Jump the demo clock to **3 Nov 2026, 09:00**, then run reminders from the bell. Check the board's reminder state and that week's digest.

The mocked analysis is intentionally scripted, not a general-purpose AI. Only the supplied Pocket debrief can be ingested in mock mode. Card edits and the displayed sample voice commands are supported; other instructions explain that the backend is needed. Audio transcription needs the backend. Mock tasks have no fake Notion/GitHub URLs, and mock reminders/heads-up notes use the `log` channel. No microphone permissions are requested: Wispr handles dictation into the focused text field.

## Routes

`/capture`, `/runs/:threadId`, `/review/:threadId`, `/memory`, `/ask`, `/board`, `/digest`.
Memory includes timeline, decision map, time machine, walk-in brief and change radar. `/review` opens a sample only in mock mode; connected sessions use their most recent run.

## Checks

```powershell
npm run build
npm run lint
npm test
```

Tests cover approval boundaries, question resolution, keeping an old decision, ripple skips, lineage direction, reminder deduplication, date snapshots, HTTP encoding/multipart and error handling.

## Integration notes

- Structured field changes use `/voice-edit` instructions because the contract has no direct review patch endpoint.
- SSE handles named events as specified, plus ordinary message events. Capture traces deliberately close at `review_ready` (supported by v1.2); execution-retry traces remain open until the pipeline terminal event. Unmount cancels subscriptions. Backend errors expose retry when allowed; a 502 after approval offers the dedicated retry endpoint rather than approving twice. A second approve/reject returns 409.
- Demo timestamps have no timezone suffix, as specified by the backend. Date-only values are formatted without local timezone shifts.
- Theme preference and mock state use separate localStorage keys. Query caches refresh after approvals, task changes, clock changes and reminders.
- Self-host the Inter fonts before offline judging if needed. The current preview loads them from Google Fonts, with system fallbacks.
- The 25 MB upload limit is a frontend prototype limit, not an API contract guarantee.
- `npm audit --omit=dev` reports zero production dependency vulnerabilities. The development-only lint toolchain currently reports 12 moderate transitive findings related to minimatch; no forced incompatible override is applied.
- Pending reviews have no listing endpoint. The last captured run is kept locally for navigation. A direct review URL can always recover another run.

The user authorized commits and pushes during the session. Publish through a `codex/` branch; do not merge backend work or modify `/backend`.
