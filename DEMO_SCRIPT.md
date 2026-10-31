# Quorum: 2-minute demo video script

**Goal of the video:** a PM watching for 2 minutes understands the problem, sees you build it by voice, and remembers one sentence: *Quorum notices when today's meeting contradicts last week's, and fixes the work that depended on it.*

Total spoken: about 270 words, read at a calm pace. Target length 2:00 (cut to 1:45 if you talk fast).

---

## Before you record (5 minutes)

1. Open the deployed link. Press the reset arrow in the top bar so memory is back to the seeded "Pocket" project. Close the other tabs and switch on Do Not Disturb.
2. Set the browser to 100% zoom, window about 1440 wide, light theme.
3. **Do one dry run first.** Wispr Flow removes "um" and adds punctuation, so what lands in the box will not match the saved sample word for word. That is fine: it then runs live on Groq, which takes a little longer than the sample. Check once that you get one conflict (launch date) before you film.
4. **Backup:** if a take goes wrong, click "Play the sample debrief" instead of speaking. It runs the same flow from saved answers and never fails.
5. Record the screen with your voice-over in one take per scene, then trim. Show the Wispr Flow bar on screen during scene 2; that is your biggest scoring item.

---

## Scenes

| Time | On screen | Say (voice-over) |
|---|---|---|
| **0:00 – 0:12** | Black or white title card: "Quorum. Meetings that remember." Then cut to the home page. | "Every team has the same fight. Three weeks after a meeting, someone says: wait, didn't we decide the opposite? Nobody remembers, and the work was already built on the old decision." |
| **0:12 – 0:35** | Home page: the big question, the voice box. Hold the Wispr key and **speak the debrief** (text below). Show the Wispr bar and the waveform moving. | "This is Quorum. You don't fill in forms. You hold Wispr Flow and just talk, the way you'd tell a colleague what happened." |
| **0:35 – 0:55** | Press Run. The five steps light up one by one: Clean up, Extract, Recall, Cross-check, Ripple. The counts appear: 1 decision, 1 task, 1 conflict. | "Quorum's agents clean up the ramble, pull out the decisions, tasks and owners, and, here's the important bit, compare every new decision with everything your team agreed before." |
| **0:55 – 1:20** | The conflict card: "20 Nov" struck through on the left, "28 Nov" on the right. Hover over Keep previous / Accept new. Click **Accept new**. | "It caught a contradiction. Last week we said launch on the 20th. Today I said the 28th. Quorum shows me both side by side, with the exact words, and I decide: keep the old one, or accept the new one." |
| **1:20 – 1:40** | Scroll to "And here's what that changes": the landing page task moves from 6 Nov to 14 Nov, and a heads-up for Priya is drafted. Toggle it off and on. Then say or type: "Move the beta testers message to Tuesday." | "And this is what no note-taker does. The landing page was planned around the old launch date, so Quorum moves it eight days, and drafts a heads-up for whoever owns it. I can switch any change off, or just say what to fix." |
| **1:40 – 1:52** | Press **Approve**. The seal animates; counts appear (1 task created, 1 decision retired, 1 heads-up sent). | "Nothing is saved or sent until I approve. One click, and the task is created, the old decision is retired, and the team gets their heads-up." |
| **1:52 – 2:00** | Click Memory (timeline), then Ask: tap "When are we launching?" and show the answer with the quoted words. End on the Quorum logo. | "Now the team has a memory. Ask 'when are we launching?' and you get the answer, with the exact words from the meeting. Quorum. Meetings that remember. Built entirely by voice with Wispr Flow." |

---

## The debrief to speak in scene 2

Say this naturally, at normal speed (about 12 seconds):

> "Okay, quick update. The launch is moving from the 20th to the 28th of November, because Apple needs a few more days to review the app. Rahul, please let the beta testers know about the new date by Monday."

What you should see: **1 decision, 1 task (Rahul, Mon 2 Nov), 1 conflict** ("Public launch is 20 Nov 2026" → "28 November 2026").

---

## On-screen captions (optional, add in editing)

- 0:12: "Hold Wispr Flow. Talk."
- 0:35: "Five agents, live"
- 0:55: "It remembers what you decided before"
- 1:20: "Ripple effect: fixes the work that depended on it"
- 1:40: "Nothing is sent until you approve"

---

## If you have 10 more seconds

Add this line before the ending, over the Memory page's "Change radar" or "Decision map" tab: *"Every decision keeps its history, so you can see exactly when and why the team changed its mind."*

---

## Caption for the upload

> We keep deciding things in meetings, then forgetting them. I built **Quorum** for the Product Space x Wispr Flow hackathon: you talk through your meeting with Wispr Flow, and an agent pipeline pulls out decisions and tasks, checks them against everything your team agreed before, flags contradictions, and fixes the work that depended on the old decision. Nothing is saved or sent until you approve.
>
> Built by voice, end to end. Try it: [your link]
>
> #WisprFlow #AgenticAI #ProductManagement #Hackathon

---

## What to say if a judge asks

- **"What's the AI doing?"** A LangGraph pipeline of agents: normalizer, extractor, memory retriever, conflict detector, ripple, executor. Models run on Groq. Conflicts are judged by the model and double-checked by plain code (dates, overloads).
- **"Why can I trust it?"** A human approves every change. Dates are re-checked by code, not only by the model. Every claim in Ask cites the exact words from the meeting.
- **"Does it connect to my tools?"** Notion first, GitHub Issues as fallback, Telegram for heads-ups. Without keys it keeps tasks on its own board instead of failing.
