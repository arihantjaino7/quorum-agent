# IDEAS.md: improvement backlog

Ideas from either agent or the user. **None of these are built until the user reviews this list**
(planned after the basic demo works). Each entry: what it is, why it helps, effort, and contract impact.

| # | Idea | Why | Effort | Contract |
|---|---|---|---|---|
| 1 | **People with roles**: `/api/people` also returns `role` (Priya: PM, Rahul: Eng lead, Ananya: Design) | UI shows titles/avatars, not bare names | S | additive field |
| 2 | **Demo stage jumps**: `POST /api/demo/reset {stage: "fresh" \| "after_debrief"}` | rehearse or recover on stage from any beat in one click | S | additive optional body |
| 3 | **Clock nudge**: `POST /api/clock {advance_hours: 24}` | a "+1 day" time-travel button instead of a date picker | S | additive optional body |
| 4 | **Auto-seed on empty DB**: first boot loads meeting 1 automatically | `uvicorn` then open the UI, no reset needed | S | none |
| 5 | **Absent-stakeholder alert**: a decision affects someone not in the meeting → auto heads-up | the "nobody told me" problem | S | maybe new Ripple kind |
| 6 | **Commitment detector**: soft promises ("I'll look into it") become low-confidence tasks | surfaces hidden work | S | additive `confidence` on Task |
| 7 | **Speak to resolve**: hold Wispr on a conflict card and say "keep Razorpay for India" | more voice in the loop (Wispr score) | S (reuses voice-edit) | none |
| 8 | **Decision confidence**: hard vs. tentative decisions; tentative ones don't ripple | fewer false alarms | M | additive field on Decision |
| 9 | **Calendar export**: `.ics` of deadlines | adoption | S | new endpoint |
| 10 | **Third seed debrief** that flips one topic back | the Flip-flop Radar shows a real A→B→A | S | none |
| 11 | **Duplicate task detection**: a debrief restating an existing task ("onboarding on track for the 3rd") links to it instead of creating a copy | cleaner board; found while testing the agreeing debrief | S | none |
