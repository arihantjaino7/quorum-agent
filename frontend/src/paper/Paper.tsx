import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
import '@fontsource/instrument-serif/400.css'
import '@fontsource/instrument-serif/400-italic.css'
import '@fontsource-variable/newsreader/wght.css'
import '@fontsource-variable/newsreader/wght-italic.css'
import '@fontsource/unifrakturmaguntia/400.css'
import '@fontsource-variable/jetbrains-mono/wght.css'
import './paper.css'
import { api, ApiError } from '@/api'
import { errorMessage } from '@/lib/utils'
import type { AgentEvent, AgentName, ApproveResult, Resolution, ReviewPayload } from '@/types'
import { FrontPage } from './front'
import { longDate } from './marks'
import { Appear, Rule, RiseLines, Stamp, Typewriter } from './parts'
import { SAMPLE_DEBRIEF, SAMPLE_SPEAKER, SAMPLE_TITLE } from './sample'

type Seen = AgentEvent & { seen: string }
type Phase = 'idle' | 'pressing' | 'review' | 'approved' | 'rejected'
const UNLOCK_KEY = 'quorum-unlocked'
const PRESS: { agent: AgentName; label: string }[] = [
  { agent: 'normalizer', label: 'Copy desk' }, { agent: 'extractor', label: 'Reporter' },
  { agent: 'memory_retriever', label: 'Archive' }, { agent: 'conflict_detector', label: 'Fact check' },
  { agent: 'ripple', label: 'Ripple' },
]
const AFTER: { agent: AgentName; label: string }[] = [
  { agent: 'executor', label: 'Dispatch' }, { agent: 'memory_writer', label: 'Archive writer' },
]
const NAV = [
  { to: '/memory', label: 'The archive' }, { to: '/ask', label: 'Ask' },
  { to: '/board', label: 'The board' }, { to: '/digest', label: 'Weekly edition' },
]

function readUnlocked() { try { return localStorage.getItem(UNLOCK_KEY) === '1' } catch { return false } }
function writeUnlocked(on: boolean) { try { if (on) localStorage.setItem(UNLOCK_KEY, '1'); else localStorage.removeItem(UNLOCK_KEY) } catch { /* nav still unlocks for this visit */ } }
const clockTime = (d: Date) => d.toTimeString().slice(0, 8)

function Wire({ events, rows, done }: { events: Seen[]; rows: { agent: AgentName; label: string }[]; done: boolean }) {
  return <ol className={`wire ${done ? 'wire-done' : ''}`} aria-live="polite">
    {rows.map(({ agent, label }, i) => {
      const own = events.filter((e) => e.agent === agent)
      const end = own.find((e) => e.type === 'agent_end')
      const last = own.at(-1)
      const state = end ? 'done' : last ? 'working' : 'waiting'
      return <motion.li key={agent} className={`wire-row is-${state}`} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}
        transition={{ delay: i * 0.06 }}>
        <span className="wire-time">{last ? last.seen : '--:--:--'}</span>
        <span className="wire-desk">{label}</span>
        <span className="wire-msg">{last ? <Typewriter key={last.message} text={last.message} /> : <span className="dim">waiting for copy…</span>}</span>
        <span className="wire-state">{state === 'done' ? (end?.run_ms ? `${(end.run_ms / 1000).toFixed(1)}s` : 'set') : state === 'working' ? <span className="ink-spin" /> : '·'}</span>
      </motion.li>
    })}
  </ol>
}

export default function Paper() {
  const client = useQueryClient()
  const [phase, setPhase] = useState<Phase>('idle')
  const [text, setText] = useState('')
  const [speaker, setSpeaker] = useState(SAMPLE_SPEAKER)
  const [usedSample, setUsedSample] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [events, setEvents] = useState<Seen[]>([])
  const [review, setReview] = useState<ReviewPayload | null>(null)
  const [failure, setFailure] = useState<{ message: string; retryable: boolean } | null>(null)
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>({})
  const [outcome, setOutcome] = useState<ApproveResult | null>(null)
  const [unlocked, setUnlocked] = useState(readUnlocked)
  const lenis = useRef<Lenis | null>(null)
  const typing = useRef<ReturnType<typeof setInterval> | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const wireRef = useRef<HTMLElement>(null)
  const frontRef = useRef<HTMLDivElement>(null)
  const filedRef = useRef<HTMLElement>(null)

  const clock = useQuery({ queryKey: ['quorum', 'clock'], queryFn: () => api.getClock() })
  const people = useQuery({ queryKey: ['quorum', 'people'], queryFn: () => api.getPeople() })
  const meetings = useQuery({ queryKey: ['quorum', 'meetings', 'Pocket'], queryFn: () => api.getMeetings('Pocket') })
  const today = (clock.data?.now ?? '2026-10-31').slice(0, 10)
  const names = people.data?.map((p) => p.name) ?? ['Priya', 'Rahul', 'Ananya']

  // Buttery scrolling for the whole page (skipped for reduced motion).
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const instance = new Lenis({ autoRaf: true, lerp: 0.09 })
    lenis.current = instance
    return () => { instance.destroy(); lenis.current = null }
  }, [])
  const scrollTo = useCallback((el: HTMLElement | null, duration = 1.6) => {
    if (!el) return
    if (lenis.current) { lenis.current.resize(); lenis.current.scrollTo(el, { offset: -16, duration }) }
    else el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  useEffect(() => () => { if (typing.current) clearInterval(typing.current) }, [])

  // Follow the run's live event stream. It stays open after review so execution shows up too.
  useEffect(() => {
    if (!threadId) return
    return api.streamRun(threadId, {
      stopAtReview: false,
      onEvent: (event) => {
        setEvents((all) => [...all, { ...event, seen: clockTime(new Date()) }])
        if (event.type === 'review_ready') {
          const payload = event.payload as ReviewPayload | undefined
          if (payload?.thread_id) setReview(payload)
          else void api.getReview(threadId).then(setReview)
          setPhase((p) => p === 'pressing' ? 'review' : p)
        }
        if (event.type === 'error') {
          const p = event.payload as { retryable?: boolean } | undefined
          setFailure({ message: event.message, retryable: Boolean(p?.retryable) })
        }
      },
      onError: (error) => setFailure({ message: error.message, retryable: false }),
    })
  }, [threadId, attempt])

  // Each new stage glides into view. On approval: back to the front page for the stamp, then on to "Filed".
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    if (phase === 'pressing') timers.push(setTimeout(() => scrollTo(wireRef.current), 650))
    if (phase === 'review') timers.push(setTimeout(() => scrollTo(frontRef.current), 400))
    if (phase === 'approved' || phase === 'rejected') {
      scrollTo(frontRef.current, 0.8)
      timers.push(setTimeout(() => scrollTo(filedRef.current, 1.8), 3300))
    }
    return () => timers.forEach(clearTimeout)
  }, [phase, scrollTo])

  const ingest = useMutation({
    mutationFn: () => api.ingest({ project: 'Pocket', title: usedSample ? SAMPLE_TITLE : 'Voice debrief', date: today, speaker, source_type: 'voice', text: text.trim() }),
    onSuccess: ({ thread_id }) => {
      try { localStorage.setItem('quorum-last-run', thread_id) } catch { /* review stays reachable by URL */ }
      setEvents([]); setReview(null); setFailure(null); setResolutions({}); setOutcome(null)
      setThreadId(thread_id); setPhase('pressing')
    },
  })
  const approve = useMutation({
    mutationFn: () => api.approve(threadId!, { resolutions }),
    onSuccess: (result) => {
      setOutcome(result); setPhase('approved'); setUnlocked(true); writeUnlocked(true)
      void client.invalidateQueries({ queryKey: ['quorum'] })
    },
  })
  const reject = useMutation({
    mutationFn: () => api.reject(threadId!),
    onSuccess: () => { setPhase('rejected'); void client.invalidateQueries({ queryKey: ['quorum'] }) },
  })
  const retry = useMutation({
    mutationFn: () => api.retryRun(threadId!),
    onSuccess: () => { setFailure(null); setEvents([]); setAttempt((n) => n + 1) },
  })
  const reset = useMutation({
    mutationFn: () => api.resetDemo(),
    onSuccess: () => { writeUnlocked(false); setUnlocked(false); client.clear(); startOver() },
  })

  function fillSample() {
    if (typing.current) clearInterval(typing.current)
    setUsedSample(true); setSpeaker(SAMPLE_SPEAKER)
    input.current?.focus()
    let n = 0
    // Types the sample in like live dictation, a few characters per frame.
    typing.current = setInterval(() => {
      n = Math.min(SAMPLE_DEBRIEF.length, n + 7)
      setText(SAMPLE_DEBRIEF.slice(0, n))
      if (n >= SAMPLE_DEBRIEF.length && typing.current) { clearInterval(typing.current); typing.current = null }
    }, 16)
  }
  function submit() {
    if (!text.trim() || ingest.isPending || typing.current) return
    ingest.mutate()
  }
  function startOver() {
    setPhase('idle'); setThreadId(null); setText(''); setUsedSample(false); setEvents([]); setReview(null)
    setFailure(null); setResolutions({}); setOutcome(null)
    if (lenis.current) lenis.current.scrollTo(0, { duration: 1.2 }); else window.scrollTo({ top: 0, behavior: 'smooth' })
    setTimeout(() => input.current?.focus(), 900)
  }

  const conflictIds = review?.conflicts.filter((c) => c.old_decision).map((c) => c.id) ?? []
  const decided = conflictIds.filter((id) => resolutions[id]).length
  const ready = decided === conflictIds.length
  const issue = issueText(approve.error) ?? issueText(reject.error)
  const executed = events.some((e) => e.agent === 'executor')

  return <div className={`paper ${phase === 'review' ? 'has-bar' : ''}`}>
    <div className="grain" aria-hidden />

    <header className="topline">
      <span className="topline-brand">Quorum</span>
      <AnimatePresence>{unlocked && <motion.nav className="topline-nav" aria-label="Sections"
        initial="hidden" animate="show" exit="hidden" variants={{ show: { transition: { staggerChildren: 0.08, delayChildren: 0.3 } } }}>
        {NAV.map((n) => <motion.span key={n.to} variants={{ hidden: { opacity: 0, y: -10 }, show: { opacity: 1, y: 0 } }}>
          <Link to={n.to}>{n.label}</Link></motion.span>)}
      </motion.nav>}</AnimatePresence>
      <span className="topline-date">{longDate(today)}</span>
    </header>

    {/* 1 · The only thing on screen at first: one question. */}
    <motion.section className="hero" animate={phase === 'idle' ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }}
      transition={{ duration: 0.9, ease: [0.76, 0, 0.24, 1] }} aria-hidden={phase !== 'idle'}>
      <div className="hero-inner">
      <RiseLines className="hero-q" delay={0.2} lines={['What happened', <>in your <em>meeting?</em></>]} />
      <Rule delay={0.9} />
      <motion.div className="hero-input" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.25, duration: 0.8 }}>
        <label className="sr-only" htmlFor="debrief">Your meeting debrief</label>
        <div className="writing">
          <textarea id="debrief" ref={input} autoFocus value={text} className={text ? '' : 'is-empty'} rows={3} spellCheck={false}
            placeholder="Hold your Wispr key and just talk. Who decided what, who owes what, by when."
            onChange={(e) => { setText(e.target.value); if (typing.current) { clearInterval(typing.current); typing.current = null } }}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit() } }}
            onInput={(e) => { const t = e.currentTarget; t.style.height = 'auto'; t.style.height = `${t.scrollHeight}px` }} />
          {!text && <span className="ink-caret" aria-hidden />}
        </div>
        <AnimatePresence mode="wait">
          {!text.trim() ? <motion.button key="sample" type="button" className="sample-link" onClick={fillSample}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            or read the sample debrief <span aria-hidden>→</span></motion.button>
          : <motion.div key="send" className="send-row" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <label className="filed-by">Filed by
              <select value={speaker} onChange={(e) => setSpeaker(e.target.value)}>{names.map((n) => <option key={n}>{n}</option>)}</select>
            </label>
            <button type="button" className="press-btn" onClick={submit} disabled={ingest.isPending}>
              {ingest.isPending ? 'Setting type…' : 'Send to press'} <span aria-hidden>→</span></button>
            <span className="hint">⌘/Ctrl + Enter</span>
          </motion.div>}
        </AnimatePresence>
        {ingest.error && <p className="ink-error" role="alert">{errorMessage(ingest.error)}</p>}
      </motion.div>
      </div>
    </motion.section>

    {/* 2 · The masthead unfurls once the debrief goes to press. */}
    <AnimatePresence>{phase !== 'idle' && <motion.div className="masthead" key="mast"
      initial={{ clipPath: 'inset(50% 0 50% 0)' }} animate={{ clipPath: 'inset(0% 0 0% 0)' }} transition={{ duration: 1, ease: [0.76, 0, 0.24, 1], delay: 0.35 }}>
      <span className="ear">No. {(meetings.data?.length ?? 1) + 1}<br />Pocket</span>
      <h1 className="mast-title">The Quorum Minutes</h1>
      <span className="ear ear-right">Meetings<br />that remember</span>
    </motion.div>}</AnimatePresence>

    {phase !== 'idle' && <section className="press" ref={wireRef}>
      <div className="press-head">
        <span className="small-caps">{review ? 'Set in type' : 'Going to press'}</span>
        <span className="small-caps dim">Live from the agents</span>
      </div>
      <Wire events={events} rows={executed || phase === 'approved' ? [...PRESS, ...AFTER] : PRESS} done={Boolean(review)} />
      {failure && <div className="stop-press" role="alert">
        <span className="correction-tag">Stop the press</span>
        <p>{failure.message}</p>
        {failure.retryable && <button type="button" className="press-btn small" disabled={retry.isPending} onClick={() => retry.mutate()}>Run it again</button>}
        <button type="button" className="text-btn" onClick={startOver}>Start over</button>
      </div>}
    </section>}

    {/* 3 · The front page assembles from the agents' output. */}
    {review && <motion.div ref={frontRef} className="front-wrap"
      animate={phase === 'approved' ? { x: [0, -7, 6, -3, 2, 0], y: [0, 3, -2, 1, 0, 0] } : { x: 0, y: 0 }} transition={{ duration: 0.45, delay: 1.05 }}>
      <FrontPage review={review} resolutions={resolutions} locked={phase !== 'review'}
        onResolve={(id, r) => setResolutions((all) => ({ ...all, [id]: r }))} />
      <AnimatePresence>
        {phase === 'approved' && <div className="stamp-spot" key="ok"><Stamp delay={0.9} label="Approved" sub={`Quorum · ${longDate(today)}`} /></div>}
        {phase === 'rejected' && <div className="stamp-spot" key="no"><Stamp delay={0.9} tone="grey" label="Spiked" sub="Nothing was filed" /></div>}
      </AnimatePresence>
    </motion.div>}

    {/* 4 · After the stamp: what got filed, and the rest of the paper opens up. */}
    {(phase === 'approved' || phase === 'rejected') && <section className="filed" ref={filedRef}>
      <Rule double />
      {phase === 'approved' ? <>
        <Appear><h2 className="filed-head">Filed. <em>The team remembers.</em></h2></Appear>
        <Appear delay={0.15} className="filed-grid">
          <div><span className="stat-n small">{outcome?.created_tasks.length ?? 0}</span><span className="small-caps">assignments on the board</span></div>
          <div><span className="stat-n small">{outcome?.superseded_ids.length ?? 0}</span><span className="small-caps">old decisions retired</span></div>
          <div><span className="stat-n small">{outcome?.heads_up_sent.length ?? 0}</span><span className="small-caps">heads-ups sent</span></div>
        </Appear>
        <Appear delay={0.3} className="filed-actions">
          <Link className="press-btn" to="/memory">Open the archive <span aria-hidden>→</span></Link>
          <button type="button" className="text-btn" onClick={startOver}>File another debrief</button>
        </Appear>
      </> : <>
        <Appear><h2 className="filed-head">Spiked. <em>Nothing changed.</em></h2></Appear>
        <Appear delay={0.15} className="filed-actions"><button type="button" className="press-btn" onClick={startOver}>File another debrief <span aria-hidden>→</span></button></Appear>
      </>}
    </section>}

    {/* The press bar: the only way anything leaves the building. */}
    <AnimatePresence>{phase === 'review' && review && <motion.div className="press-bar" key="bar"
      initial={{ y: '120%' }} animate={{ y: 0, transition: { duration: 0.7, ease: [0.76, 0, 0.24, 1], delay: 0.8 } }}
      exit={{ y: '140%', transition: { duration: 0.45, ease: [0.76, 0, 0.24, 1] } }}>
      <div className="press-bar-copy">
        <strong>{conflictIds.length ? (ready ? 'Every correction has a ruling.' : `${conflictIds.length - decided} correction${conflictIds.length - decided > 1 ? 's' : ''} need your ruling`) : 'Nothing contradicts the record.'}</strong>
        <span>{issue ?? 'Nothing is filed, sent or remembered until you approve.'}</span>
      </div>
      <div className="press-bar-actions">
        {!ready && <button type="button" className="text-btn" onClick={() => setResolutions(Object.fromEntries(conflictIds.map((id) => [id, 'accept_new' as const])))}>Accept all new</button>}
        <button type="button" className="ghost-btn" disabled={reject.isPending || approve.isPending} onClick={() => reject.mutate()}>Reject</button>
        <button type="button" className="press-btn" disabled={!ready || approve.isPending || reject.isPending} onClick={() => approve.mutate()}>
          {approve.isPending ? 'Stamping…' : 'Approve'} <span aria-hidden>→</span></button>
      </div>
    </motion.div>}</AnimatePresence>

    <footer className="colophon">
      <span>Quorum · meetings that remember · built by voice</span>
      {unlocked && <button type="button" className="text-btn" disabled={reset.isPending} onClick={() => reset.mutate()}>Reset the demo</button>}
    </footer>
  </div>
}

/** 409 means someone already ruled on this run; anything else is shown as-is. */
function issueText(error: Error | null): string | null {
  if (!error) return null
  if (error instanceof ApiError && error.status === 409) return 'This debrief was already ruled on. Start over to file another.'
  return errorMessage(error)
}
