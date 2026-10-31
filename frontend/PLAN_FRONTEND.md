# Quorum frontend build plan

Updated 31 October 2026 after the user supplied Rekora as the visual reference and authorized frontend commits and pushes during the session. Work stays in this workspace; the user will integrate `/frontend` with the backend checkout. No backend changes.

## Visual direction
Rekora-inspired warm stone `#EEEDE9`, paper surfaces, near-black text, one burgundy accent, Inter Tight headlines, Inter body, fine borders, pill controls, rounded cards. Quorum keeps its own voice and content. Use animation to explain agent progress and reveal conflicts. Preserve native scrolling and pointer behavior; honor reduced motion. Adapt the guide's patterns to React and the originally requested framer-motion stack rather than copying its standalone DOM-mutating scripts.

## Phase 1 — foundation and contract
Vite/React/TypeScript/Tailwind/shadcn-compatible local components; all routes; TanStack Query; a fully typed client for CONTRACT.md v1.2; stateful, explicit Pocket mocks; `/api` proxy. Light/dark tokens, responsive shell and accessible state components.

Acceptance: build/typecheck/lint pass; actual HTTP client serializes contract requests; no frontend code enters `/backend`; mock actions cannot create external tracker links or claim external delivery.

## Phase 2 — review and conflict reveal (first product priority)
Old/new decisions, source meetings, affected-task counts, per-conflict Accept new/Keep previous, cleaned/original text, inline corrections and accessible original-word tooltips, editable decision/task fields, unresolved questions, spoken edits with change diffs, approve/reject outcomes. Add v1.1 ripple choices and personal heads-up previews.

Acceptance: three Pocket conflicts can be inspected independently; approval remains disabled until questions and choices are resolved; keeping a prior decision skips associated updates; mutations invalidate shared memory/board/digest caches; external effects are labelled honestly in demo mode.

## Phase 3 — capture and live agent trace
Voice-first text capture (Wispr types into a focused field), metadata, text/transcript/audio file input, sample-story shortcut, upload validation, cancellable SSE pipeline, terminal success/error recovery. No built-in microphone impersonation or invented live listening status.

Acceptance: sample capture → five-agent progress → review → approval → board works. Uploads go through multipart; arbitrary analysis requires the backend and is never replaced silently by sample results.

## Phase 4 — shared memory and team execution
Meeting timeline and superseded decisions, React Flow lineage, cited Ask answers, owner-grouped task board with status mutations/reminder badges, person/week markdown digests. Add v1.1 time-machine snapshots, walk-in brief and change radar as views inside Memory rather than extra top-level navigation.

Acceptance: source links identify the originating meeting; graph arrows run new → superseded; approved changes appear across screens; demo clock determines reminders and digest weeks.

## Phase 5 — finishing and integration
Desktop/mobile and both themes; keyboard focus; reduced-motion behavior; meaningful empty/loading/error states; actual browser checks of the demo path. Contract drift and backend limitations documented. Commit and push only frontend files, the permitted root context file, and append-only voice-log updates to a `codex/` branch during the session. Leave backend integration and merge reviewable.

The earlier first-session instruction required approval before product screens. The subsequent request supplied a UI guide and asked to make the prototype, extending that first-session scope. Further direction can be applied without rebuilding the foundation.
