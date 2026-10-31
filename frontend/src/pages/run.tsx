import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Check, Circle, LoaderCircle, ShieldCheck } from 'lucide-react'
import { api } from '@/api'
import { PageHeading, ErrorState } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { AgentEvent, AgentName, ReviewPayload } from '@/types'

const steps: { agent: AgentName; label: string; detail: string }[] = [
  { agent: 'normalizer', label: 'Normalizer', detail: 'A little clarity, without losing your meaning.' },
  { agent: 'extractor', label: 'Extractor', detail: 'Decisions, commitments, and the people behind them.' },
  { agent: 'memory_retriever', label: 'Memory', detail: 'Every new conversation meets what came before.' },
  { agent: 'conflict_detector', label: 'Conflict check', detail: 'Finding the changes that deserve a second look.' },
  { agent: 'ripple', label: 'Ripple effect', detail: 'Following each change into work already underway.' },
]
export default function Run() {
  const { threadId = '' } = useParams()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const [resuming, setResuming] = useState(params.get('resuming') === '1')
  const [retryable, setRetryable] = useState(false)
  const [completed, setCompleted] = useState<'approved' | 'rejected' | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [attempt, setAttempt] = useState(0)
  const retry = useMutation({ mutationFn: () => api.retryRun(threadId), onSuccess: () => {
    setError(null); setEvents([]); setReady(false); setResuming(true); setAttempt((n) => n + 1)
  }, onError: setError })
  useEffect(() => {
    return api.streamRun(threadId, { stopAtReview: !resuming, onEvent: (event) => {
      setEvents((all) => [...all, event])
      if (event.type === 'error') {
        setError(new Error(event.message))
        setRetryable(Boolean(event.payload && typeof event.payload === 'object' && 'retryable' in event.payload && event.payload.retryable))
      }
      if (event.type === 'agent_end' && event.agent === 'pipeline' && event.payload && typeof event.payload === 'object' && 'status' in event.payload) {
        if (event.payload.status === 'approved' || event.payload.status === 'rejected') {
          setCompleted(event.payload.status); void queryClient.invalidateQueries({ queryKey: ['quorum'] })
        }
      }
      if (event.type === 'review_ready') {
        const payload = event.payload as ReviewPayload | undefined
        if (payload?.thread_id) queryClient.setQueryData(['quorum', 'review', threadId], payload)
        setReady(true)
      }
    }, onError: setError })
  }, [threadId, queryClient, attempt, resuming])
  const visibleSteps = resuming ? [...steps,
    { agent: 'executor' as const, label: 'Executor', detail: 'Turning confirmed commitments into work.' },
    { agent: 'memory_writer' as const, label: 'Memory writer', detail: 'Remembering the direction you chose.' },
  ] : steps
  return <>
    <PageHeading number="02" eyebrow="A FEW AGENTS. ONE SHARED MEMORY." title="Connecting the dots." soft="Keeping you in the loop." description="Quorum is working through your debrief, checking every new commitment against your team’s history." />
    <Card className="trace-card"><div className="trace-heading"><span className="tag"><span className="status-dot" />{ready ? 'Ready for you' : 'Agents at work'}</span><span className="muted">Nothing is sent before your approval.</span></div>
      <ol className="trace-list">{visibleSteps.map(({ agent, label, detail }, index) => {
        const agentEvents = events.filter((e) => e.agent === agent)
        const complete = agentEvents.some((e) => e.type === 'agent_end')
        const active = !complete && agentEvents.some((e) => e.type === 'agent_start')
        return <li key={agent} className={`trace-step ${complete ? 'complete' : ''} ${active ? 'working' : ''}`}><span className="trace-node">{complete ? <Check size={16} /> : active ? <LoaderCircle className="spin" size={16} /> : <span>{String(index + 1).padStart(2, '0')}</span>}</span><div><h3>{label}</h3><AnimatePresence mode="wait"><motion.p key={agentEvents.at(-1)?.message ?? detail} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{agentEvents.at(-1)?.message ?? detail}</motion.p></AnimatePresence></div><span className="trace-status">{complete ? 'Complete' : active ? 'Working' : 'Waiting'}</span></li>
      })}<li className={`trace-step ${ready ? 'working' : ''}`}><span className="trace-node">{ready ? <ShieldCheck size={17} /> : <Circle size={15} />}</span><div><h3>Awaiting you</h3><p>{ready ? 'Three conflicts surfaced. Your judgment takes it from here.' : 'The most important decision-maker is still you.'}</p></div><span className="trace-status">{ready ? 'Your turn' : 'Waiting'}</span></li></ol>
      {ready && !resuming && <motion.div className="trace-ready" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div><strong>What’s changed deserves a closer look.</strong><p>Your debrief is ready. Review the decisions before they become commitments.</p></div><Button asChild><Link to={`/review/${encodeURIComponent(threadId)}`}>Review decisions<ArrowRight size={15} /></Link></Button></motion.div>}
      {completed && <div className="trace-ready"><div><strong>{completed === 'approved' ? 'Your commitments are ready.' : 'This debrief was set aside.'}</strong><p>The run is complete. Your shared memory reflects the outcome.</p></div><Button asChild><Link to={completed === 'approved' ? '/board' : '/capture'}>Continue<ArrowRight size={15} /></Link></Button></div>}
    </Card>
    {error && <ErrorState error={error} retry={retry.isPending ? undefined : () => { if (retryable) retry.mutate(); else { setError(null); setEvents([]); setReady(false); setAttempt((n) => n + 1) } }} />}
    {error && <p className="quiet-empty">The run may still be processing. <Link className="source-link" to={`/review/${encodeURIComponent(threadId)}`}>Check for a saved review<ArrowRight size={13} /></Link></p>}
  </>
}
