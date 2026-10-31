import type { QuorumApi, StreamOptions } from './contracts'
import { ApiError } from './errors'
import type { AgentEvent } from '@/types'

function query(values: Record<string, string | boolean | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) params.set(key, String(value))
  }
  return params.size ? `?${params}` : ''
}

export function createHttpApi(baseUrl = '/api'): QuorumApi {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    let response: Response
    try {
      response = await fetch(`${baseUrl}${path}`, { ...init, headers })
    } catch (error) {
      throw new ApiError('Cannot reach Quorum. Check the backend connection and try again.', 0, error)
    }
    const text = await response.text()
    let body: unknown
    try { body = text ? JSON.parse(text) : undefined } catch { body = text }
    if (!response.ok) {
      const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body
      const message = typeof detail === 'string' && detail.trim()
        ? detail : `Request failed (${response.status}). Please try again.`
      throw new ApiError(message, response.status, body)
    }
    return body as T
  }
  const post = <T>(path: string, body?: unknown) => request<T>(path, {
    method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  const run = (id: string) => `/runs/${encodeURIComponent(id)}`

  return {
    ingest: (input) => post('/ingest', input),
    ingestFile: (input) => {
      const form = new FormData()
      const { file, ...metadata } = input
      form.append('file', file)
      for (const [key, value] of Object.entries(metadata)) form.append(key, value)
      return request('/ingest/file', { method: 'POST', body: form })
    },
    streamRun: (id, options) => subscribe(`${baseUrl}${run(id)}/stream`, options),
    getReview: (id) => request(`${run(id)}/review`),
    voiceEdit: (id, instruction) => post(`${run(id)}/voice-edit`, { instruction }),
    approve: (id, input) => post(`${run(id)}/approve`, input),
    reject: (id) => post(`${run(id)}/reject`),
    retryRun: (id) => post(`${run(id)}/retry`),
    getProjects: () => request('/projects'),
    getMeetings: (project) => request(`/meetings${query({ project })}`),
    getPeople: () => request('/people'),
    getDecisions: (filters = {}) => request(`/decisions${query({ ...filters })}`),
    getDecisionGraph: (project) => request(`/decisions/graph${query({ project })}`),
    getTasks: (filters = {}) => request(`/tasks${query({ ...filters })}`),
    updateTask: (id, status) => request(`/tasks/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
    ask: (project, question) => post('/ask', { project, question }),
    getDigest: (person, weekOf) => request(`/digest/${encodeURIComponent(person)}${query({ week_of: weekOf })}`),
    getClock: () => request('/clock'),
    setClock: (now) => post('/clock', { now }),
    runReminders: () => post('/reminders/run'),
    resetDemo: async () => { await post<unknown>('/demo/reset') },
    getHealth: () => request('/health'),
    getBrief: (project) => request(`/brief${query({ project })}`),
    getRadar: (project) => request(`/radar${query({ project })}`),
    getDecisionsAsOf: (project, date) => request(`/decisions/as-of${query({ project, date })}`),
    getDecisionTimeline: (project, topicKey) => request(`/decisions/timeline${query({ project, topic_key: topicKey })}`),
  }
}

function subscribe(url: string, { onEvent, onError, stopAtReview = true }: StreamOptions) {
  const source = new EventSource(url)
  let closed = false
  const close = () => { closed = true; source.close() }
  const receive = (message: MessageEvent<string>) => {
    if (closed) return
    let event: AgentEvent
    try { event = JSON.parse(message.data) as AgentEvent } catch {
      close()
      onError?.(new ApiError('Quorum returned an unreadable agent event.', 502))
      return
    }
    if ((event.type === 'review_ready' && stopAtReview) || event.type === 'error'
      || (event.type === 'agent_end' && event.agent === 'pipeline')) close()
    onEvent(event)
  }
  // Support both `data: {...}` and named SSE events without changing the wire payload.
  source.onmessage = receive
  for (const type of ['agent_start', 'agent_progress', 'agent_end', 'review_ready', 'error']) {
    source.addEventListener(type, (event) => {
      if ('data' in event) receive(event as MessageEvent<string>)
    })
  }
  source.onerror = (event) => {
    if (closed || 'data' in event) return
    close()
    onError?.(new ApiError('The agent stream disconnected. Reopen the run to recover its review.', 0))
  }
  return close
}
