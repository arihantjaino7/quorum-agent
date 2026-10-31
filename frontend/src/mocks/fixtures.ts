import type { Decision, Meeting, ReviewPayload, Task } from '@/types'

export const DEMO_NOW = '2026-10-31T09:00:00'
export const DEMO_THREAD = 'demo-investor-sync'
export const people = ['Priya', 'Rahul', 'Ananya']
export const previousMeeting: Meeting = {
  id: 'meeting-kickoff', project: 'Pocket', title: 'The v1 game plan', date: '2026-10-24',
  speaker: 'Priya', source_type: 'voice',
}

export const oldDecisions: Decision[] = [
  { id: 'decision-ios', topic_key: 'platform_scope', statement: 'Keep v1 iOS-only. Android comes after launch.', made_by: 'Priya',
    meeting_id: previousMeeting.id, date: previousMeeting.date, status: 'active', superseded_by: null,
    rationale: 'Keep the first release focused with our small team.', source_quote: 'Let’s keep v1 iOS-only and pick up Android after launch.' },
  { id: 'decision-launch', topic_key: 'launch_date', statement: 'Launch Pocket on 20 November 2026.', made_by: 'Rahul',
    meeting_id: previousMeeting.id, date: previousMeeting.date, status: 'active', superseded_by: null,
    rationale: 'Have a working product ready for the investor update.', source_quote: 'We are committing to the 20th of November.' },
  { id: 'decision-payments', topic_key: 'payments_provider', statement: 'Use Razorpay for payments in v1.', made_by: 'Ananya',
    meeting_id: previousMeeting.id, date: previousMeeting.date, status: 'active', superseded_by: null,
    rationale: 'Start with a familiar payment provider.', source_quote: 'Razorpay is our payment provider for v1.' },
]

export const existingTasks: Task[] = [
  { id: 'task-onboarding', title: 'Design iOS onboarding screens', owner: 'Priya', due_date: '2026-11-04', raw_due_phrase: 'next Wednesday',
    status: 'todo', source_quote: 'Priya, take the iOS onboarding screens by next Wednesday.', meeting_id: previousMeeting.id, tracker_url: null, reminder_sent: false },
  { id: 'task-razorpay', title: 'Complete Razorpay integration', owner: 'Ananya', due_date: '2026-11-06', raw_due_phrase: 'by the 6th',
    status: 'todo', source_quote: 'Ananya will complete the Razorpay integration by the 6th.', meeting_id: previousMeeting.id, tracker_url: null, reminder_sent: false },
  { id: 'task-launch-checklist', title: 'Prepare the launch checklist', owner: 'Rahul', due_date: '2026-11-18', raw_due_phrase: 'two days before launch',
    status: 'todo', source_quote: 'Rahul, have the launch checklist ready two days before launch.', meeting_id: previousMeeting.id, tracker_url: null, reminder_sent: false },
  { id: 'task-research', title: 'Share first-round user interviews', owner: 'Priya', due_date: '2026-10-29', raw_due_phrase: 'Thursday',
    status: 'done', source_quote: 'Priya will share the user interviews on Thursday.', meeting_id: previousMeeting.id, tracker_url: null, reminder_sent: false },
]

export const demoDebrief = `Okay, so quick debrief from the investor sync. Um, Rahul said we need Android back in v1 because the investors want both platforms at launch. Priya will update onboarding for iOS and Android by next Wednesday. Oh, and the coffee machine is still broken, someone should really fix that. Anyway, launch is December 1st — no wait, November 28th. Rahul, get the Play Store listing ready by November 18th. And we're dropping Razorpay. The KYC is taking too long, so Ananya will switch us to Stripe by November 12th. Someone also needs to send the investor update; we didn't decide who or when.`

export const cleanDebrief = `Rahul confirmed that Android is back in v1: investors want both platforms at launch. Priya will update onboarding for iOS and Android by 4 November 2026.\n\nThe launch moves to 28 November 2026. Rahul will prepare the Play Store listing by 18 November 2026.\n\nSwitch from Razorpay to Stripe because Razorpay KYC is taking too long. Ananya will complete the Stripe integration by 12 November 2026.\n\nSend an investor update. The owner and deadline still need to be confirmed.`

export function makeReview(threadId = DEMO_THREAD): ReviewPayload {
  const meeting: Meeting = { id: `${threadId}-meeting`, project: 'Pocket', title: 'Investor sync debrief',
    date: '2026-10-31', speaker: 'Priya', source_type: 'voice' }
  const decisions: Decision[] = [
    { id: `${threadId}-android`, topic_key: 'platform_scope', statement: 'Ship v1 on iOS and Android.', made_by: 'Rahul', meeting_id: meeting.id,
      date: meeting.date, status: 'pending', superseded_by: null, rationale: 'Investors want both platforms at launch.', source_quote: 'Rahul confirmed that Android is back in v1: investors want both platforms at launch.' },
    { id: `${threadId}-launch`, topic_key: 'launch_date', statement: 'Move the launch to 28 November 2026.', made_by: 'Priya', meeting_id: meeting.id,
      date: meeting.date, status: 'pending', superseded_by: null, rationale: 'Allow time for the expanded launch scope.', source_quote: 'The launch moves to 28 November 2026.' },
    { id: `${threadId}-stripe`, topic_key: 'payments_provider', statement: 'Switch payments from Razorpay to Stripe.', made_by: 'Ananya', meeting_id: meeting.id,
      date: meeting.date, status: 'pending', superseded_by: null, rationale: 'Razorpay KYC is taking too long.', source_quote: 'Switch from Razorpay to Stripe because Razorpay KYC is taking too long.' },
  ]
  const tasks: Task[] = [
    { id: `${threadId}-listing`, title: 'Prepare the Play Store listing', owner: 'Rahul', due_date: '2026-11-18', raw_due_phrase: 'by November 18th',
      status: 'pending', source_quote: 'Rahul, get the Play Store listing ready by November 18th.', meeting_id: meeting.id, tracker_url: null, reminder_sent: false },
    { id: `${threadId}-integration`, title: 'Complete the Stripe integration', owner: 'Ananya', due_date: '2026-11-12', raw_due_phrase: 'by November 12th',
      status: 'pending', source_quote: 'Ananya will switch us to Stripe by November 12th.', meeting_id: meeting.id, tracker_url: null, reminder_sent: false },
    { id: `${threadId}-investor`, title: 'Send the investor update', owner: '', due_date: null, raw_due_phrase: '',
      status: 'pending', source_quote: "Someone also needs to send the investor update; we didn't decide who or when.", meeting_id: meeting.id, tracker_url: null, reminder_sent: false },
  ]
  return {
    thread_id: threadId, meeting, raw_text: demoDebrief, clean_text: cleanDebrief,
    corrections: [
      { original: 'December 1st — no wait, November 28th', resolved: '28 November 2026', kind: 'self_correction' },
      { original: 'Um,', resolved: '', kind: 'filler' },
      { original: 'Oh, and the coffee machine is still broken, someone should really fix that.', resolved: '', kind: 'digression' },
      { original: 'next Wednesday', resolved: '4 November 2026', kind: 'date_resolution' },
    ],
    decisions, tasks,
    conflicts: [
      { id: `${threadId}-scope-conflict`, type: 'reversal', severity: 'high', new_item_id: decisions[0].id, old_decision: oldDecisions[0],
        affected_tasks: [existingTasks[0]], explanation: 'Android re-enters v1 a week after the team committed to iOS-only. Onboarding already in progress needs a wider scope.',
        suggested_resolution: 'Confirm both platforms and update the existing onboarding task.' },
      { id: `${threadId}-launch-conflict`, type: 'deadline_collision', severity: 'medium', new_item_id: decisions[1].id, old_decision: oldDecisions[1],
        affected_tasks: [existingTasks[2]], explanation: 'The launch moves eight days later. The existing launch checklist is still tied to the old date.',
        suggested_resolution: 'Accept 28 November and move the launch checklist to 26 November.' },
      { id: `${threadId}-payments-conflict`, type: 'contradiction', severity: 'high', new_item_id: decisions[2].id, old_decision: oldDecisions[2],
        affected_tasks: [existingTasks[1]], explanation: 'Stripe replaces the approved Razorpay decision. Ananya has an open Razorpay integration task that will become obsolete.',
        suggested_resolution: 'Confirm Stripe and cancel the old Razorpay integration task.' },
    ],
    questions: [
      { id: `${threadId}-owner-question`, item_id: tasks[2].id, field: 'owner', prompt: 'Who owns the investor update?' },
      { id: `${threadId}-date-question`, item_id: tasks[2].id, field: 'due_date', prompt: 'When is the investor update due?' },
    ],
    ripples: [
      { id: `${threadId}-rescope`, conflict_id: `${threadId}-scope-conflict`, decision_id: decisions[0].id, kind: 'rescope', task: existingTasks[0],
        reason: 'Onboarding was designed for iOS only. Android is now back in v1.', proposal: { title: 'Design iOS and Android onboarding screens' }, default_action: 'apply' },
      { id: `${threadId}-reschedule`, conflict_id: `${threadId}-launch-conflict`, decision_id: decisions[1].id, kind: 'reschedule', task: existingTasks[2],
        reason: 'Keep the checklist two days before the revised launch.', proposal: { due_date: '2026-11-26', raw_due_phrase: 'two days before the revised launch' }, default_action: 'apply' },
      { id: `${threadId}-cancel`, conflict_id: `${threadId}-payments-conflict`, decision_id: decisions[2].id, kind: 'cancel', task: existingTasks[1],
        reason: 'Razorpay integration is no longer needed after the switch to Stripe.', proposal: {}, default_action: 'apply' },
    ],
    heads_up: [
      { person: 'Priya', message_md: 'Your onboarding work now covers **iOS and Android**. Your deadline stays **4 November**.', ripple_ids: [`${threadId}-rescope`], task_ids: [existingTasks[0].id] },
      { person: 'Rahul', message_md: 'Launch moves to **28 November**. Your checklist can move to **26 November**; the Play Store listing is due **18 November**.', ripple_ids: [`${threadId}-reschedule`], task_ids: [existingTasks[2].id, tasks[0].id] },
      { person: 'Ananya', message_md: 'Stop the Razorpay integration. We’re moving to **Stripe**, due **12 November**.', ripple_ids: [`${threadId}-cancel`], task_ids: [existingTasks[1].id, tasks[1].id] },
    ],
  }
}
