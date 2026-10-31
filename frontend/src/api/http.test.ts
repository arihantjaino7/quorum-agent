import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpApi } from './http'
import type { AgentEvent } from '@/types'

class TestEventSource extends EventTarget {
  static current: TestEventSource
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  close = vi.fn()
  constructor() { super(); TestEventSource.current = this }
  emit(event: AgentEvent) { this.dispatchEvent(new MessageEvent(event.type, { data: JSON.stringify(event) })) }
}

afterEach(() => vi.unstubAllGlobals())
describe('HTTP contract boundaries', () => {
  it('preserves ISO dates and encodes opaque IDs, people, and query values', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}', { status: 200 })))
    vi.stubGlobal('fetch', fetch)
    const api = createHttpApi()
    await api.getReview('id/with spaces')
    expect(fetch.mock.calls[0][0]).toBe('/api/runs/id%2Fwith%20spaces/review')
    await api.getDecisions({ project: 'Pocket & Co', include_superseded: false })
    expect(fetch.mock.calls[1][0]).toBe('/api/decisions?project=Pocket+%26+Co&include_superseded=false')
    await api.getDigest('Priya Jain', '2026-10-26')
    expect(fetch.mock.calls[2][0]).toBe('/api/digest/Priya%20Jain?week_of=2026-10-26')
  })

  it('lets the browser set the multipart boundary and sends metadata without a text field', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"thread_id":"new-run"}'))
    vi.stubGlobal('fetch', fetch)
    const file = new File(['meeting text'], 'meeting.txt', { type: 'text/plain' })
    await createHttpApi().ingestFile({ project: 'Pocket', title: 'Debrief', date: '2026-10-31', speaker: 'Priya', source_type: 'transcript', file })
    const [, options] = fetch.mock.calls[0]
    expect(options.headers.has('Content-Type')).toBe(false)
    expect(options.body.get('date')).toBe('2026-10-31')
    expect(options.body.has('text')).toBe(false)
    expect(options.body.get('file').name).toBe('meeting.txt')
  })

  it('surfaces backend validation details, empty reset responses, and network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response('{"detail":"The run is still processing"}', { status: 409 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 })).mockRejectedValueOnce(new TypeError('offline')))
    const api = createHttpApi()
    await expect(api.getReview('running')).rejects.toMatchObject({ status: 409, message: 'The run is still processing' })
    await expect(api.resetDemo()).resolves.toBeUndefined()
    await expect(api.getClock()).rejects.toMatchObject({ status: 0 })
  })

  it('supports the v1.2 execution stream through its pipeline terminal event', () => {
    vi.stubGlobal('EventSource', TestEventSource)
    const events: AgentEvent[] = []
    createHttpApi().streamRun('retry-run', { stopAtReview: false, onEvent: (event) => events.push(event) })
    const source = TestEventSource.current
    source.emit({ type: 'review_ready', agent: 'pipeline', message: 'Review', ts: '2026-10-31T09:00:00' })
    expect(source.close).not.toHaveBeenCalled()
    source.emit({ type: 'agent_end', agent: 'executor', message: 'Created tasks', ts: '2026-10-31T09:00:01' })
    expect(source.close).not.toHaveBeenCalled()
    source.emit({ type: 'agent_end', agent: 'pipeline', message: 'Complete', ts: '2026-10-31T09:00:02', payload: { status: 'approved' } })
    expect(source.close).toHaveBeenCalledOnce()
    expect(events).toHaveLength(3)
  })

  it('allows a capture trace to stop at review and sends retry to the dedicated endpoint', async () => {
    vi.stubGlobal('EventSource', TestEventSource)
    const onEvent = vi.fn()
    const api = createHttpApi()
    api.streamRun('run', { onEvent })
    TestEventSource.current.emit({ type: 'review_ready', agent: 'pipeline', message: 'Review', ts: '2026-10-31T09:00:00' })
    expect(TestEventSource.current.close).toHaveBeenCalledOnce()
    const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}'))
    vi.stubGlobal('fetch', fetch)
    await api.retryRun('id/opaque')
    expect(fetch.mock.calls[0][0]).toBe('/api/runs/id%2Fopaque/retry')
    expect(fetch.mock.calls[0][1].method).toBe('POST')
  })
})
