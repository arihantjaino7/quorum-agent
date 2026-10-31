import { describe, expect, it } from 'vitest'
import { createMockApi } from './api'
import { DEMO_THREAD, demoDebrief } from './fixtures'
import type { AgentEvent } from '@/types'

const makeApi = () => createMockApi({ latency: 0, persist: false, streamDelay: 1 })

describe('Pocket demo lifecycle', () => {
  it('keeps extracted commitments out of tasks and memory before approval', async () => {
    const api = makeApi()
    const review = await api.getReview(DEMO_THREAD)
    expect(review.conflicts).toHaveLength(3)
    expect(review.questions).toHaveLength(2)
    expect(review.ripples).toHaveLength(3)
    expect((await api.getDecisions()).every((d) => d.status === 'active')).toBe(true)
    expect((await api.getTasks()).some((t) => review.tasks.some((pending) => pending.id === t.id))).toBe(false)
    await expect(api.approve(DEMO_THREAD, { resolutions: {} })).rejects.toMatchObject({ status: 422 })
  })

  it('accepts a real sample ingest and emits a terminal review payload', async () => {
    const api = makeApi()
    const { thread_id } = await api.ingest({ project: 'Pocket', title: 'Investor sync', date: '2026-10-31', speaker: 'Priya', source_type: 'voice', text: demoDebrief })
    const events: AgentEvent[] = []
    await new Promise<void>((resolve, reject) => {
      api.streamRun(thread_id, { onEvent: (event) => { events.push(event); if (event.type === 'review_ready') resolve() }, onError: reject })
    })
    expect(events.filter((e) => e.type === 'agent_end')).toHaveLength(5)
    expect(events.at(-1)).toMatchObject({ type: 'review_ready', payload: { thread_id } })
    expect((await api.getMeetings('Pocket'))[0].title).toBe('Investor sync')
  })

  it('never presents Pocket fixture extraction as analysis of arbitrary user text', async () => {
    const api = makeApi()
    await expect(api.ingest({ project: 'Pocket', title: 'Different meeting', date: '2026-10-31', speaker: 'Priya', source_type: 'voice', text: 'We decided to build a garden.' })).rejects.toMatchObject({ status: 422 })
  })

  it('resolves inline questions through the same voice-edit API used by cards', async () => {
    const api = makeApi()
    const title = 'Send the investor update'
    const owner = await api.voiceEdit(DEMO_THREAD, `Set task "${title}" owner to "Priya"`)
    expect(owner.review.questions).toHaveLength(1)
    const due = await api.voiceEdit(DEMO_THREAD, `Set task "${title}" due_date to "2026-11-05"`)
    expect(due.review.questions).toHaveLength(0)
    expect(due.review.tasks.find((t) => t.title === title)).toMatchObject({ owner: 'Priya', due_date: '2026-11-05' })
  })

  it('applies downstream updates, writes lineage, and rejects repeat approval', async () => {
    const api = makeApi()
    await api.voiceEdit(DEMO_THREAD, 'Drop the investor update')
    const outcome = await api.approve(DEMO_THREAD, { resolutions: {} })
    expect(outcome.created_tasks).toHaveLength(2)
    expect(outcome.superseded_ids).toHaveLength(3)
    expect(outcome.updated_tasks).toHaveLength(2)
    expect(outcome.cancelled_task_ids).toEqual(['task-razorpay'])
    expect(outcome.heads_up_sent.every((h) => h.channel === 'log')).toBe(true)
    expect((await api.getTasks()).every((t) => t.tracker_url === null)).toBe(true)
    const graph = await api.getDecisionGraph('Pocket')
    expect(graph.edges).toHaveLength(3)
    expect(graph.edges.every((edge) => outcome.superseded_ids.includes(edge.target))).toBe(true)
    await expect(api.approve(DEMO_THREAD, { resolutions: {} })).rejects.toMatchObject({ status: 409 })
    expect(await api.getDecisions({ include_superseded: true })).toHaveLength(6)
  })

  it('preserves old scope, skips its ripple, and respects an explicit skip action', async () => {
    const api = makeApi()
    const { review } = await api.voiceEdit(DEMO_THREAD, 'Drop the investor update')
    const outcome = await api.approve(DEMO_THREAD, {
      resolutions: { [review.conflicts[0].id]: 'keep_old' }, ripple_actions: { [review.ripples[1].id]: 'skip' },
    })
    expect(outcome.created_tasks.map((t) => t.owner)).toEqual(['Ananya'])
    expect(outcome.updated_tasks).toHaveLength(0)
    const tasks = await api.getTasks()
    expect(tasks.find((t) => t.id === 'task-onboarding')?.title).toBe('Design iOS onboarding screens')
    expect(tasks.find((t) => t.id === 'task-launch-checklist')?.due_date).toBe('2026-11-18')
    expect((await api.getDecisions()).some((d) => d.id === 'decision-ios')).toBe(true)
  })

  it('rejects without creating tasks or changing remembered decisions', async () => {
    const api = makeApi()
    const before = await api.getTasks()
    await api.reject(DEMO_THREAD)
    expect(await api.getTasks()).toEqual(before)
    expect(await api.getDecisions()).toHaveLength(3)
    await expect(api.voiceEdit(DEMO_THREAD, 'Drop the investor update')).rejects.toMatchObject({ status: 409 })
    await expect(api.approve(DEMO_THREAD, { resolutions: {} })).rejects.toMatchObject({ status: 409 })
    await expect(api.retryRun(DEMO_THREAD)).rejects.toMatchObject({ status: 409 })
  })

  it('keeps the full stream open through approval when the client asks for execution events', async () => {
    const api = makeApi()
    await api.voiceEdit(DEMO_THREAD, 'Drop the investor update')
    const events: AgentEvent[] = []
    await new Promise<void>((resolve, reject) => {
      api.streamRun(DEMO_THREAD, { stopAtReview: false, onError: reject, onEvent: (event) => {
        events.push(event)
        if (event.type === 'review_ready') void api.approve(DEMO_THREAD, { resolutions: {} }).catch(reject)
        if (event.type === 'agent_end' && event.agent === 'pipeline') resolve()
      } })
    })
    expect(events[0]).toMatchObject({ type: 'agent_start', agent: 'pipeline' })
    expect(events.some((event) => event.agent === 'executor')).toBe(true)
    expect(events.at(-1)?.payload).toMatchObject({ status: 'approved' })
  })

  it('uses the demo clock for reminder deduplication and digest weeks', async () => {
    const api = makeApi()
    await api.setClock('2026-11-03T09:00:00')
    expect((await api.getDigest('Priya')).week_of).toBe('2026-11-02')
    expect((await api.runReminders()).sent).toEqual([{ task_id: 'task-onboarding', owner: 'Priya', channel: 'log' }])
    expect((await api.runReminders()).sent).toHaveLength(0)
    await api.resetDemo()
    expect((await api.getClock()).now).toBe('2026-10-31T09:00:00')
    expect((await api.getTasks()).find((t) => t.id === 'task-onboarding')?.reminder_sent).toBe(false)
  })

  it('answers from approved decisions and reconstructs earlier truth after approval', async () => {
    const api = makeApi()
    expect((await api.ask('Pocket', 'Why Razorpay?')).answer).toContain('familiar payment provider')
    await api.voiceEdit(DEMO_THREAD, 'Drop the investor update')
    await api.approve(DEMO_THREAD, { resolutions: {} })
    const answer = await api.ask('Pocket', 'Why did we drop Razorpay?')
    expect(answer.answer).toContain('KYC')
    expect(answer.citations[0].date).toBe('2026-10-31')
    const snapshot = await api.getDecisionsAsOf('Pocket', '2026-10-24')
    expect(snapshot.decisions.every((d) => d.status === 'active')).toBe(true)
    expect(snapshot.changed_since).toHaveLength(3)
    expect((await api.getRadar('Pocket')).topics.every((t) => t.versions === 2)).toBe(true)
  })
})
