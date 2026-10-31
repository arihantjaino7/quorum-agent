import type { QuorumApi } from '@/api/contracts'
import { ApiError } from '@/api/errors'
import type { AgentEvent, ApproveResult, Decision, Digest, IngestInput, Meeting, RadarTopic, ReviewPayload, Task } from '@/types'
import { DEMO_NOW, DEMO_THREAD, demoDebrief, existingTasks, makeReview, oldDecisions, people, previousMeeting } from './fixtures'

interface MockState {
  version: 1
  now: string
  decisions: Decision[]
  tasks: Task[]
  meetings: Meeting[]
  runs: Record<string, ReviewPayload>
  outcomes: Record<string, ApproveResult | 'rejected'>
  nextRun: number
}
const STORAGE_KEY = 'quorum-demo-v1'
const clone = <T>(value: T): T => structuredClone(value)
const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const topicLabel = (key: string) => ({ platform_scope: 'Platform scope', launch_date: 'Launch date', payments_provider: 'Payments provider' })[key] ?? key.replaceAll('_', ' ')

function freshState(): MockState {
  return clone({ version: 1, now: DEMO_NOW, decisions: oldDecisions, tasks: existingTasks,
    meetings: [previousMeeting], runs: { [DEMO_THREAD]: makeReview() }, outcomes: {}, nextRun: 1 })
}
function readState(): MockState {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as MockState | null
    if (saved?.version === 1 && saved.runs && saved.outcomes) return saved
  } catch { /* Private browsing and unit tests can run without browser storage. */ }
  return freshState()
}
function monday(date: string) {
  const day = new Date(`${date.slice(0, 10)}T00:00:00Z`)
  day.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7)
  return day.toISOString().slice(0, 10)
}

/** A scripted Pocket demo, never a pretend general-purpose language model. */
export function createMockApi({ latency = 180, persist = true, streamDelay = 380 } = {}): QuorumApi {
  let state = persist ? readState() : freshState()
  const streams = new Set<() => void>()
  const executionListeners = new Map<string, Set<(event: AgentEvent) => void>>()
  function emitExecution(id: string, event: Omit<AgentEvent, 'ts'>) {
    executionListeners.get(id)?.forEach((listener) => listener({ ...event, ts: state.now }))
  }
  const save = () => {
    if (!persist) return
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* Storage is optional. */ }
  }
  async function result<T>(value: T): Promise<T> { await wait(latency); return clone(value) }
  function review(id: string) {
    const value = state.runs[id]
    if (!value) throw new ApiError('This meeting run could not be found.', 404)
    return value
  }
  function editable(id: string) {
    if (state.outcomes[id]) throw new ApiError('This review has already been completed. Start a new debrief or reset the demo.', 409)
    return review(id)
  }
  function projectDecisions(project?: string) {
    const meetingIds = new Set(state.meetings.filter((m) => !project || m.project === project).map((m) => m.id))
    return state.decisions.filter((d) => meetingIds.has(d.meeting_id))
  }
  function projectTasks(project?: string, owner?: string) {
    const meetingIds = new Set(state.meetings.filter((m) => !project || m.project === project).map((m) => m.id))
    return state.tasks.filter((t) => meetingIds.has(t.meeting_id) && (!owner || t.owner === owner))
  }
  function radar(project = 'Pocket'): RadarTopic[] {
    const decisions = projectDecisions(project)
    return [...new Set(decisions.map((d) => d.topic_key))].map((key) => {
      const versions = decisions.filter((d) => d.topic_key === key).sort((a, b) => a.date.localeCompare(b.date))
      const flips = Math.max(0, versions.length - 1)
      return {
        topic_key: key, label: topicLabel(key), versions: versions.length, flips,
        last_changed: versions.at(-1)!.date, churn: Math.min(1, flips / 3), risk: flips ? 'medium' as const : 'low' as const,
        statements: versions.map((d) => ({ decision_id: d.id, date: d.date, statement: d.statement, made_by: d.made_by })),
        note: flips ? 'This decision changed. Confirm the current direction before starting more work.' : 'One clear decision. No reversals recorded.',
      }
    }).sort((a, b) => b.churn - a.churn)
  }
  function digest(person: string, weekOf?: string): Digest {
    const start = weekOf ?? monday(state.now)
    const end = new Date(`${start}T00:00:00Z`)
    end.setUTCDate(end.getUTCDate() + 7)
    const endDate = end.toISOString().slice(0, 10)
    const tasks = state.tasks.filter((t) => t.owner === person)
    const done = tasks.filter((t) => t.status === 'done' && t.due_date && t.due_date >= start && t.due_date < endDate)
    const overdue = tasks.filter((t) => t.status === 'todo' && t.due_date && t.due_date < state.now.slice(0, 10))
    const due = tasks.filter((t) => t.status === 'todo' && t.due_date && t.due_date >= start && t.due_date < endDate && !overdue.includes(t))
    const decisions = state.decisions.filter((d) => d.made_by === person && d.date >= start && d.date < endDate)
    return { person, week_of: start, summary_md: `## Your week, ${person}.\n\nYou have **${due.length} tasks due this week**, **${done.length} completed**, and **${overdue.length} overdue**.\n\n${due.length ? 'Focus on the commitments below. Each one links back to the meeting where it started.' : 'No upcoming deadlines in this week. Your other commitments are on the task board.'}`,
      done, due, overdue, decisions, conflicts: Object.entries(state.runs).filter(([id]) => !state.outcomes[id]).flatMap(([, r]) => r.conflicts.filter((c) => c.affected_tasks.some((t) => t.owner === person))) }
  }
  async function ingest(input: IngestInput) {
    if (input.project !== 'Pocket' || input.text.trim() !== demoDebrief.trim()) {
      throw new ApiError('The local demo uses the Pocket sample debrief. Choose “Try the demo”, or switch VITE_USE_MOCKS=false to process your own words with the backend.', 422)
    }
    const id = `pocket-run-${state.nextRun++}`
    const value = makeReview(id)
    value.meeting = { ...value.meeting, project: input.project, title: input.title, date: input.date, speaker: input.speaker, source_type: input.source_type }
    // Relative dates in this scripted story are anchored to 31 October 2026.
    if (input.date !== '2026-10-31') throw new ApiError('The sample debrief is anchored to 31 October 2026. Use that meeting date for this demo.', 422)
    state.runs[id] = value
    state.meetings.unshift(value.meeting)
    save()
    return result({ thread_id: id })
  }
  return {
    ingest,
    ingestFile: async ({ file, ...fields }) => {
      if (fields.source_type === 'audio') throw new ApiError('Audio transcription needs the backend. The local demo supports its sample text only.', 422)
      return ingest({ ...fields, text: await file.text() })
    },
    streamRun: (id, { onEvent, onError, stopAtReview = true }) => {
      let stopped = false
      const timers: ReturnType<typeof setTimeout>[] = []
      const emit = (event: AgentEvent) => {
        if (stopped) return
        onEvent(clone(event))
        if (event.type === 'agent_end' && event.agent === 'pipeline') close()
      }
      const close = () => { stopped = true; timers.forEach(clearTimeout); streams.delete(close); executionListeners.get(id)?.delete(emit) }
      streams.add(close)
      let value: ReviewPayload
      try { value = clone(review(id)) } catch (error) {
        timers.push(setTimeout(() => { if (!stopped) onError?.(error as Error); close() }, latency))
        return close
      }
      const steps = [
        ['normalizer', 'Making room for the important parts.', 'Removed fillers, resolved two dates, kept the meaning.'],
        ['extractor', 'Finding decisions and commitments.', 'Found 3 decisions, 3 new tasks and 2 open questions.'],
        ['memory_retriever', 'Looking back through Pocket’s memory.', 'Recalled 3 decisions from “The v1 game plan”.'],
        ['conflict_detector', 'Checking what changed.', 'Found 3 conflicts with previously approved decisions.'],
        ['ripple', 'Following the effect on existing work.', '3 existing tasks are affected. Nothing changes without you.'],
      ] as const
      const events: AgentEvent[] = [{ type: 'agent_start', agent: 'pipeline', message: `Run started for ${value.meeting.title}`, ts: state.now }, ...steps.flatMap(([agent, start, end]) => [
        { type: 'agent_start', agent, message: start, ts: state.now },
        { type: 'agent_end', agent, message: end, ts: state.now, run_ms: streamDelay },
      ] as AgentEvent[])]
      events.push({ type: 'review_ready', agent: 'pipeline', message: 'Ready for your review.', payload: value, ts: state.now })
      const outcome = state.outcomes[id]
      if (outcome) events.push({ type: 'agent_end', agent: 'pipeline', message: outcome === 'rejected' ? 'The debrief was rejected.' : 'Your commitments are ready.',
        payload: outcome === 'rejected' ? { status: 'rejected' } : { status: 'approved', ...outcome }, ts: state.now })
      if (!stopAtReview) {
        const listeners = executionListeners.get(id) ?? new Set()
        listeners.add(emit); executionListeners.set(id, listeners)
      }
      events.forEach((event, index) => timers.push(setTimeout(() => {
        if (stopped) return
        onEvent(clone(event))
        if ((event.type === 'review_ready' && stopAtReview) || (event.type === 'agent_end' && event.agent === 'pipeline')) close()
      }, (index + 1) * streamDelay)))
      return close
    },
    getReview: (id) => result(editable(id)),
    voiceEdit: async (id, instruction) => {
      const value = clone(editable(id))
      const changes: string[] = []
      const lower = instruction.toLowerCase()
      for (const task of value.tasks) {
        const explicit = instruction.match(/^Set task "(.+)" (owner|due_date|title) to "(.*)"\.?$/i)
        if (explicit?.[1] === task.title) {
          const [, , field, content] = explicit
          if (field === 'owner' && !people.includes(content)) throw new ApiError('Choose Priya, Rahul or Ananya in the Pocket demo.', 422)
          if (field === 'due_date' && !/^2026-\d{2}-\d{2}$/.test(content)) throw new ApiError('Enter an ISO date, such as 2026-11-18.', 422)
          if (field === 'owner') task.owner = content
          if (field === 'due_date') task.due_date = content
          if (field === 'title') task.title = content
          changes.push(`${task.title}: ${field.replace('_', ' ')} → ${content}`)
        }
        if (!explicit && task.owner === 'Rahul' && /rahul/i.test(instruction) && /18th|november 18|2026-11-18/.test(lower)) {
          const old = task.due_date
          task.due_date = '2026-11-18'
          changes.push(`${task.title}: ${old} → 2026-11-18`)
        }
        if (!explicit && /investor update/.test(lower) && /send|assign|own/.test(lower) && task.id.endsWith('-investor')) {
          const person = people.find((p) => lower.includes(p.toLowerCase()))
          if (person) { task.owner = person; changes.push(`Investor update: owner → ${person}`) }
          const date = instruction.match(/2026-\d{2}-\d{2}/)?.[0]
          if (date) { task.due_date = date; changes.push(`Investor update: due date → ${date}`) }
        }
      }
      if (/drop|remove/.test(lower) && /investor update/.test(lower)) {
        value.tasks = value.tasks.filter((t) => !t.id.endsWith('-investor'))
        changes.push('Removed task: Send the investor update')
      }
      const decisionEdit = instruction.match(/^Change decision "(.+)" to "(.+)"\.?$/i)
      if (decisionEdit) {
        const item = value.decisions.find((d) => d.statement === decisionEdit[1])
        if (item) { changes.push(`Decision: ${item.statement} → ${decisionEdit[2]}`); item.statement = decisionEdit[2] }
      }
      if (!changes.length) throw new ApiError('This scripted demo supports editing card fields, “drop the investor update”, or “assign the investor update to Priya, due 2026-11-05”. Connect the backend for other spoken edits.', 422)
      value.questions = value.questions.filter((q) => {
        const task = value.tasks.find((t) => t.id === q.item_id)
        return task && (q.field === 'owner' ? !task.owner : !task.due_date)
      })
      state.runs[id] = value
      save()
      return result({ review: value, changes })
    },
    approve: async (id, input) => {
      const value = editable(id)
      if (value.questions.length) throw new ApiError('Resolve the unanswered task questions before approving.', 422)
      const outcome: ApproveResult = { created_tasks: [], superseded_ids: [], updated_tasks: [], cancelled_task_ids: [], heads_up_sent: [] }
      emitExecution(id, { type: 'agent_start', agent: 'executor', message: 'Turning approved commitments into tasks.' })
      if (!state.meetings.some((m) => m.id === value.meeting.id)) state.meetings.unshift(clone(value.meeting))
      const kept = new Set(value.conflicts.filter((c) => input.resolutions[c.id] === 'keep_old').map((c) => c.new_item_id))
      for (const decision of value.decisions.filter((d) => !kept.has(d.id))) {
        for (const old of state.decisions.filter((d) => d.topic_key === decision.topic_key && d.status === 'active')) {
          old.status = 'superseded'; old.superseded_by = decision.id; outcome.superseded_ids.push(old.id)
        }
        state.decisions.push({ ...clone(decision), status: 'active' })
      }
      for (const task of value.tasks) {
        const topic = task.id.endsWith('-listing') ? 'platform_scope' : task.id.endsWith('-integration') ? 'payments_provider' : null
        if (topic && value.decisions.some((d) => d.topic_key === topic && kept.has(d.id))) continue
        const created: Task = { ...clone(task), status: 'todo' }
        // No fake tracker URLs: the mock has no external integrations.
        state.tasks.push(created); outcome.created_tasks.push(clone(created))
      }
      const applied = new Set<string>()
      for (const ripple of value.ripples) {
        if (kept.has(ripple.decision_id) || (input.ripple_actions?.[ripple.id] ?? ripple.default_action) === 'skip') continue
        const index = state.tasks.findIndex((t) => t.id === ripple.task?.id)
        if (index < 0) continue
        applied.add(ripple.id)
        if (ripple.kind === 'cancel') { outcome.cancelled_task_ids.push(state.tasks[index].id); state.tasks.splice(index, 1) }
        else { Object.assign(state.tasks[index], ripple.proposal); outcome.updated_tasks.push(clone(state.tasks[index])) }
      }
      outcome.heads_up_sent = value.heads_up.filter((h) => h.ripple_ids.some((r) => applied.has(r))).map((h) => ({ person: h.person, channel: 'log' }))
      emitExecution(id, { type: 'agent_end', agent: 'executor', message: `${outcome.created_tasks.length} tasks created in the local demo.`, run_ms: latency })
      emitExecution(id, { type: 'agent_start', agent: 'memory_writer', message: 'Remembering your confirmed decisions.' })
      state.outcomes[id] = outcome
      save()
      emitExecution(id, { type: 'agent_end', agent: 'memory_writer', message: 'Your team’s memory is up to date.', run_ms: latency })
      emitExecution(id, { type: 'agent_end', agent: 'pipeline', message: 'Your commitments are ready.', payload: { status: 'approved', ...outcome } })
      return result(outcome)
    },
    reject: (id) => { editable(id); state.outcomes[id] = 'rejected'; save(); emitExecution(id, { type: 'agent_end', agent: 'pipeline', message: 'The debrief was rejected.', payload: { status: 'rejected' } }); return result({ ok: true }) },
    retryRun: async (id) => { review(id); throw new ApiError('This demo run has not failed. Only failed runs can be retried.', 409) },
    getProjects: () => result([...new Set(state.meetings.map((m) => m.project))].map((name) => ({ name,
      meeting_count: state.meetings.filter((m) => m.project === name).length,
      last_meeting: state.meetings.find((m) => m.project === name)!.date }))),
    getMeetings: (project) => result(state.meetings.filter((m) => !project || m.project === project).sort((a, b) => b.date.localeCompare(a.date))),
    getPeople: () => result(people.map((name) => ({ name, open_tasks: state.tasks.filter((t) => t.owner === name && t.status === 'todo').length,
      overdue: state.tasks.filter((t) => t.owner === name && t.status === 'todo' && t.due_date && t.due_date < state.now.slice(0, 10)).length }))),
    getDecisions: ({ project, include_superseded = false } = {}) => result(projectDecisions(project).filter((d) => include_superseded || d.status !== 'superseded')),
    getDecisionGraph: (project) => {
      const decisions = projectDecisions(project)
      return result({ nodes: decisions.map((d) => ({ id: d.id, label: d.statement, status: d.status, date: d.date,
        meeting_title: state.meetings.find((m) => m.id === d.meeting_id)?.title ?? 'Meeting' })),
      edges: decisions.filter((d) => d.superseded_by).map((d) => ({ source: d.superseded_by!, target: d.id, kind: 'supersedes' as const })) })
    },
    getTasks: ({ project, owner } = {}) => result(projectTasks(project, owner)),
    updateTask: (id, status) => {
      const task = state.tasks.find((t) => t.id === id)
      if (!task) throw new ApiError('This task could not be found.', 404)
      task.status = status; save(); return result(task)
    },
    ask: (project, question) => {
      const lower = question.toLowerCase()
      const topic = /razorpay|stripe|payment/.test(lower) ? 'payments_provider' : /android|ios|platform/.test(lower) ? 'platform_scope' : /launch|date|when/.test(lower) ? 'launch_date' : null
      const decisions = projectDecisions(project).filter((d) => !topic || d.topic_key === topic)
      const active = decisions.filter((d) => d.status === 'active')
      const answer = !topic ? 'Try asking about the launch date, platform scope, or payment provider in this scripted demo. Connect the backend for broader questions.'
        : active.length ? active.map((d) => `${d.statement} ${d.rationale ?? ''}`).join('\n\n') : 'There is no approved decision about that in this project yet.'
      return result({ answer, citations: topic ? active.map((d) => ({ meeting_id: d.meeting_id,
        meeting_title: state.meetings.find((m) => m.id === d.meeting_id)?.title ?? 'Meeting', date: d.date, quote: d.source_quote ?? d.statement })) : [] })
    },
    getDigest: (person, weekOf) => result(digest(person, weekOf)),
    getClock: () => result({ now: state.now }),
    setClock: (now) => {
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(now) || Number.isNaN(Date.parse(now))) throw new ApiError('Enter a valid demo timestamp.', 422)
      state.now = now; save(); return result({ now })
    },
    runReminders: () => {
      const now = Date.parse(`${state.now}Z`)
      const sent = state.tasks.filter((t) => {
        const due = t.due_date ? Date.parse(`${t.due_date}T00:00:00Z`) : NaN
        return t.status === 'todo' && !t.reminder_sent && due >= now && due <= now + 86_400_000
      }).map((t) => { t.reminder_sent = true; return { task_id: t.id, owner: t.owner, channel: 'log' } })
      save(); return result({ sent })
    },
    resetDemo: async () => { streams.forEach((close) => close()); state = freshState(); save(); await wait(latency) },
    getHealth: () => result({ ok: true, version: '0.1.0', replay: true, clock: state.now,
      integrations: { groq: false, notion: false, github: false, telegram: false } }),
    getRadar: (project = 'Pocket') => result({ project, topics: radar(project) }),
    getBrief: (project = 'Pocket') => {
      const tasks = projectTasks(project).filter((t) => t.status === 'todo')
      const dueSoon = tasks.filter((t) => t.due_date && t.due_date >= state.now.slice(0, 10) && t.due_date <= new Date(Date.parse(`${state.now}Z`) + 7 * 86_400_000).toISOString().slice(0, 10))
      const decisions = projectDecisions(project).filter((d) => d.status === 'active')
      return result({ project, as_of: state.now, headline: decisions.map((d) => d.statement).join(' '),
        script_md: `## Before you walk in\n\n${decisions.map((d) => `- **${topicLabel(d.topic_key)}:** ${d.statement}`).join('\n')}\n\n${dueSoon.length} tasks are due in the next seven days.`,
        agenda: ['Confirm platform scope before more design work starts.', 'Check payment integration progress.', 'Review the next launch milestone.'],
        open_conflicts: Object.entries(state.runs).filter(([id]) => !state.outcomes[id]).flatMap(([, r]) => r.conflicts),
        overdue: tasks.filter((t) => t.due_date && t.due_date < state.now.slice(0, 10)), due_soon: dueSoon, hot_topics: radar(project) })
    },
    getDecisionsAsOf: (project, date) => {
      const all = projectDecisions(project)
      const current = all.filter((d) => d.status === 'active')
      const snapshot = [...new Set(all.map((d) => d.topic_key))].flatMap((key) => {
        const then = all.filter((d) => d.topic_key === key && d.date <= date).sort((a, b) => b.date.localeCompare(a.date))[0]
        return then ? [{ ...then, status: 'active' as const, superseded_by: null }] : []
      })
      return result({ project, date, decisions: snapshot,
        changed_since: snapshot.flatMap((then) => { const now = current.find((d) => d.topic_key === then.topic_key); return now && now.id !== then.id ? [{ topic_key: then.topic_key, then, now }] : [] }) })
    },
    getDecisionTimeline: (project, topicKey) => {
      const decisions = projectDecisions(project)
      return result({ topics: [...new Set(decisions.map((d) => d.topic_key))].filter((key) => !topicKey || key === topicKey).map((key) => ({ topic_key: key, label: topicLabel(key),
        events: decisions.filter((d) => d.topic_key === key).sort((a, b) => a.date.localeCompare(b.date)).map((d, index) => ({ decision: d, meeting_id: d.meeting_id,
          meeting_title: state.meetings.find((m) => m.id === d.meeting_id)?.title ?? 'Meeting', date: d.date, made_by: d.made_by, quote: d.source_quote ?? '', change: index ? 'reversed' as const : 'created' as const })) })) })
    },
  }
}
