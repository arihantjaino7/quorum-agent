import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, ArrowUpRight, AudioLines, BrainCircuit, CheckCheck, FileUp, LoaderCircle, Moon, RotateCcw, ShieldCheck, Sun } from 'lucide-react'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
import './home.css'
import { api, ApiError } from '@/api'
import { useApp } from '@/lib/app-context'
import { errorMessage } from '@/lib/utils'
import type { ApproveResult, Resolution, ReviewPayload } from '@/types'
import { Pipeline, Results, type Seen } from './sections'
import { Appear, CountUp, RiseWords, Seal, Waveform } from './motion'
import { AFTER, EASE, EASE_IN_OUT, STEPS } from './constants'
import { SAMPLE_DEBRIEF, SAMPLE_SPEAKER, SAMPLE_TITLE } from './sample'

type Phase = 'idle' | 'running' | 'review' | 'approved' | 'rejected'
const UNLOCK_KEY = 'quorum-unlocked'
const NAV = [{ to: '/memory', label: 'Memory' }, { to: '/ask', label: 'Ask' }, { to: '/board', label: 'Board' }, { to: '/digest', label: 'Digest' }]
const HOW = [
  { icon: AudioLines, title: 'Talk it through', body: 'Hold your Wispr key and ramble. No forms.' },
  { icon: BrainCircuit, title: 'Quorum checks memory', body: 'Every decision is compared with what your team agreed before.' },
  { icon: ShieldCheck, title: 'You approve', body: 'Nothing is sent or saved until you say so.' },
]

function readUnlocked() { try { return localStorage.getItem(UNLOCK_KEY) === '1' } catch { return false } }
function writeUnlocked(on: boolean) { try { if (on) localStorage.setItem(UNLOCK_KEY, '1'); else localStorage.removeItem(UNLOCK_KEY) } catch { /* unlocks for this visit only */ } }
function issueText(error: Error | null) {
  if (!error) return null
  return error instanceof ApiError && error.status === 409 ? 'Someone already decided on this debrief. Start a new one.' : errorMessage(error)
}

export default function Home() {
  const { theme, toggleTheme } = useApp()
  const client = useQueryClient()
  const [phase, setPhase] = useState<Phase>('idle')
  const [text, setText] = useState('')
  const [speaker, setSpeaker] = useState(SAMPLE_SPEAKER)
  const [usedSample, setUsedSample] = useState(false)
  const [focused, setFocused] = useState(false)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [events, setEvents] = useState<Seen[]>([])
  const [review, setReview] = useState<ReviewPayload | null>(null)
  const [failure, setFailure] = useState<{ message: string; retryable: boolean } | null>(null)
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>({})
  const [outcome, setOutcome] = useState<ApproveResult | null>(null)
  const [rippleActions, setRippleActions] = useState<Record<string, 'apply' | 'skip'>>({})
  const [changes, setChanges] = useState<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const [unlocked, setUnlocked] = useState(readUnlocked)
  const lenis = useRef<Lenis | null>(null)
  const typing = useRef<ReturnType<typeof setInterval> | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const runRef = useRef<HTMLElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const doneRef = useRef<HTMLElement>(null)

  const clock = useQuery({ queryKey: ['quorum', 'clock'], queryFn: () => api.getClock() })
  const people = useQuery({ queryKey: ['quorum', 'people'], queryFn: () => api.getPeople() })
  const today = (clock.data?.now ?? '2026-10-31').slice(0, 10)
  const names = people.data?.map((p) => p.name) ?? ['Priya', 'Rahul', 'Ananya']

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const instance = new Lenis({ autoRaf: true, lerp: 0.09 })
    lenis.current = instance
    return () => { instance.destroy(); lenis.current = null }
  }, [])
  const scrollTo = useCallback((el: HTMLElement | null, duration = 1.5) => {
    if (!el) return
    if (lenis.current) { lenis.current.resize(); lenis.current.scrollTo(el, { offset: -88, duration }) }
    else el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  useEffect(() => () => { if (typing.current) clearInterval(typing.current) }, [])

  // Live agent events. The stream stays open after review, so execution shows up too.
  useEffect(() => {
    if (!threadId) return
    return api.streamRun(threadId, {
      stopAtReview: false,
      onEvent: (event) => {
        setEvents((all) => [...all, { ...event, seen: Date.now() }])
        if (event.type === 'review_ready') {
          const payload = event.payload as ReviewPayload | undefined
          if (payload?.thread_id) setReview(payload)
          else void api.getReview(threadId).then(setReview)
          setPhase((p) => p === 'running' ? 'review' : p)
        }
        if (event.type === 'error') {
          const p = event.payload as { retryable?: boolean } | undefined
          setFailure({ message: event.message, retryable: Boolean(p?.retryable) })
        }
      },
      onError: (error) => setFailure({ message: error.message, retryable: false }),
    })
  }, [threadId, attempt])

  // Each stage glides into view.
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []
    if (phase === 'running') timers.push(setTimeout(() => scrollTo(runRef.current), 500))
    if (phase === 'review') timers.push(setTimeout(() => scrollTo(resultsRef.current), 700))
    if (phase === 'approved' || phase === 'rejected') timers.push(setTimeout(() => scrollTo(doneRef.current, 1.2), 150))
    return () => timers.forEach(clearTimeout)
  }, [phase, scrollTo])

  const started = ({ thread_id }: { thread_id: string }) => {
      try { localStorage.setItem('quorum-last-run', thread_id) } catch { /* reachable by URL too */ }
      setEvents([]); setReview(null); setFailure(null); setResolutions({}); setOutcome(null); setRippleActions({}); setChanges([])
      setThreadId(thread_id); setPhase('running')
    }
  const ingest = useMutation({
    mutationFn: () => api.ingest({ project: 'Pocket', title: usedSample ? SAMPLE_TITLE : 'Voice debrief', date: today, speaker, source_type: 'voice', text: text.trim() }),
    onSuccess: started,
  })
  const upload = useMutation({
    mutationFn: (file: File) => api.ingestFile({ project: 'Pocket', title: file.name.replace(/\.[^.]+$/, ''), date: today, speaker, source_type: 'transcript', file }),
    onSuccess: started,
  })
  const edit = useMutation({
    mutationFn: (instruction: string) => api.voiceEdit(threadId!, instruction),
    onSuccess: (result) => { setReview(result.review); setChanges(result.changes) },
  })
  const approve = useMutation({
    mutationFn: () => api.approve(threadId!, { resolutions, ripple_actions: rippleActions }),
    onSuccess: (result) => { setOutcome(result); setPhase('approved'); setUnlocked(true); writeUnlocked(true); void client.invalidateQueries({ queryKey: ['quorum'] }) },
  })
  const reject = useMutation({
    mutationFn: () => api.reject(threadId!),
    onSuccess: () => { setPhase('rejected'); void client.invalidateQueries({ queryKey: ['quorum'] }) },
  })
  const retry = useMutation({ mutationFn: () => api.retryRun(threadId!), onSuccess: () => { setFailure(null); setEvents([]); setAttempt((n) => n + 1) } })
  const reset = useMutation({ mutationFn: () => api.resetDemo(), onSuccess: () => { writeUnlocked(false); setUnlocked(false); client.clear(); startOver() } })

  function fillSample() {
    if (typing.current) clearInterval(typing.current)
    setUsedSample(true); setSpeaker(SAMPLE_SPEAKER); input.current?.focus()
    let n = 0
    typing.current = setInterval(() => {
      n = Math.min(SAMPLE_DEBRIEF.length, n + 6)
      setText(SAMPLE_DEBRIEF.slice(0, n))
      if (n >= SAMPLE_DEBRIEF.length && typing.current) { clearInterval(typing.current); typing.current = null }
    }, 18)
  }
  function submit() { if (text.trim() && !ingest.isPending && !typing.current) ingest.mutate() }
  function startOver() {
    setPhase('idle'); setThreadId(null); setText(''); setUsedSample(false); setEvents([]); setReview(null)
    setFailure(null); setResolutions({}); setOutcome(null); setRippleActions({}); setChanges([])
    if (lenis.current) lenis.current.scrollTo(0, { duration: 1.2 }); else window.scrollTo({ top: 0, behavior: 'smooth' })
    setTimeout(() => input.current?.focus(), 900)
  }

  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  const conflictIds = review?.conflicts.filter((c) => c.old_decision).map((c) => c.id) ?? []
  const decided = conflictIds.filter((id) => resolutions[id]).length
  const ready = decided === conflictIds.length
  const issue = issueText(approve.error) ?? issueText(reject.error)
  const executing = events.some((e) => e.agent === 'executor')
  const startAt = events[0]?.seen
  const readyAt = events.find((e) => e.type === 'review_ready')?.seen
  const live = focused || text.length > 0

  return <div className={`home ${phase === 'review' ? 'has-bar' : ''}`} onMouseMove={(e) => {
    e.currentTarget.style.setProperty('--px', `${e.clientX}px`); e.currentTarget.style.setProperty('--py', `${e.clientY}px`)
  }}>
    <div className="ambient" aria-hidden><span className="blob b1" /><span className="blob b2" /><span className="blob b3" /><span className="grid" /><span className="cursor-glow" /></div>

    <header className="home-bar">
      <Link to="/" className="brand" aria-label="Quorum home" onClick={(e) => { if (phase !== 'idle') { e.preventDefault(); startOver() } }}>
        <span className="brand-mark">q<span /></span><span>quorum<span className="brand-period">.</span></span>
      </Link>
      <AnimatePresence>{unlocked && <motion.nav className="home-nav" aria-label="Workspace" initial="hidden" animate="show" exit="hidden"
        variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: 0.4 } } }}>
        {NAV.map((n) => <motion.span key={n.to} variants={{ hidden: { opacity: 0, y: -12, filter: 'blur(6px)' }, show: { opacity: 1, y: 0, filter: 'blur(0px)' } }}>
          <Link to={n.to}>{n.label}</Link></motion.span>)}
      </motion.nav>}</AnimatePresence>
      <div className="home-bar-actions">
        {unlocked && <button type="button" className="icon-pill" title="Reset the demo" aria-label="Reset the demo" disabled={reset.isPending} onClick={() => reset.mutate()}><RotateCcw size={15} /></button>}
        <button type="button" className="icon-pill" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={toggleTheme}>{theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}</button>
      </div>
    </header>

    {/* 1 · One question, one box. */}
    <motion.section className="hero" animate={phase === 'idle' ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }}
      transition={{ duration: 0.9, ease: EASE_IN_OUT }} aria-hidden={phase !== 'idle'}>
      <div className="hero-inner">
        <motion.span className="eyebrow-pill" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}>
          <i />Meetings that remember
        </motion.span>
        <RiseWords className="hero-title" delay={0.15} lines={[{ text: 'What happened in' }, { text: 'your meeting?', muted: true }]} />
        <motion.p className="hero-sub" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.85, duration: 0.8, ease: EASE }}>
          Say it out loud. Quorum pulls out the decisions and tasks, and tells you when they contradict what your team already agreed.
        </motion.p>

        <motion.div className={`voice-card ${live ? 'is-live' : ''}`} initial={{ opacity: 0, y: 30, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 1.05, duration: 1, ease: EASE }}>
          <div className="voice-card-inner">
            <div className="voice-top">
              <span className={`mic ${live ? 'is-live' : ''}`}><AudioLines size={18} /></span>
              <Waveform level={text.length} />
              <span className="voice-hint">{text ? `${words} words` : 'Hold Wispr · speak'}</span>
            </div>
            <label className="sr-only" htmlFor="debrief">Your meeting debrief</label>
            <textarea id="debrief" ref={input} value={text} rows={3} autoFocus spellCheck={false}
              placeholder="“Rahul said Android is back in v1, launch moves to the 28th, Ananya redoes onboarding by Wednesday…”"
              onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
              onChange={(e) => { setText(e.target.value); if (typing.current) { clearInterval(typing.current); typing.current = null } }}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit() } }} />
            <div className="voice-bottom">
              <label className="speaker">Debrief by
                <select value={speaker} onChange={(e) => setSpeaker(e.target.value)}>{names.map((n) => <option key={n}>{n}</option>)}</select>
              </label>
              <button type="button" className="run-btn" disabled={!text.trim() || ingest.isPending} onClick={submit}>
                {ingest.isPending ? <><LoaderCircle size={16} className="spin" />Starting…</> : <>Run Quorum<ArrowRight size={16} /></>}
              </button>
            </div>
          </div>
        </motion.div>
        {ingest.error && <p className="error-line" role="alert">{errorMessage(ingest.error)}</p>}

        <AnimatePresence>{!text && <motion.button type="button" className="sample-chip" onClick={fillSample}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: 1.5, duration: 0.6 } }} exit={{ opacity: 0, y: 6 }}>
          <span className="sample-dot" />No mic handy? <b>Play the sample debrief</b><ArrowRight size={14} />
        </motion.button>}</AnimatePresence>

        <input ref={fileInput} type="file" accept=".txt,.md,.vtt,.srt,.mp3,.m4a,.wav,.webm" hidden aria-label="Upload a transcript"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = '' }} />
        <button type="button" className="upload-link" disabled={upload.isPending} onClick={() => fileInput.current?.click()}>
          {upload.isPending ? <LoaderCircle size={14} className="spin" /> : <FileUp size={14} />}Or upload a transcript or recording (.txt .vtt .srt .mp3)</button>
        {upload.error && <p className="error-line" role="alert">{errorMessage(upload.error)}</p>}

        <div className="how">{HOW.map((h, i) => <motion.div key={h.title} className="how-step" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.7 + i * 0.12, duration: 0.7, ease: EASE }}>
          <span className="how-icon"><h.icon size={16} /></span><div><strong>{h.title}</strong><p>{h.body}</p></div>
        </motion.div>)}</div>
      </div>
    </motion.section>

    {/* 2 · Agents at work. */}
    {phase !== 'idle' && <section className="run" ref={runRef}>
      <motion.div className="run-head" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE, delay: 0.3 }}>
        <span className="eyebrow-pill"><i className={review ? '' : 'is-busy'} />{review ? 'Done' : 'Agents at work'}</span>
        <h2>{review ? 'Here’s what changed.' : 'Reading between the lines…'}</h2>
        <p>{review && startAt && readyAt ? `Five agents, ${((readyAt - startAt) / 1000).toFixed(1)} seconds, checked against everything your team decided before.`
          : 'Five agents clean your words, pull out decisions and tasks, and check them against team memory.'}</p>
      </motion.div>
      <Pipeline events={events} steps={executing || phase === 'approved' ? [...STEPS, ...AFTER] : STEPS} />
      {failure && <div className="run-error" role="alert"><strong>Something stopped the run.</strong><p>{failure.message}</p>
        <div>{failure.retryable && <button type="button" className="run-btn small" disabled={retry.isPending} onClick={() => retry.mutate()}>Try again</button>}
          <button type="button" className="link-btn" onClick={startOver}>Start over</button></div></div>}
    </section>}

    {/* 3 · Results. */}
    {review && <div ref={resultsRef} className="results-wrap">
      <Results review={review} resolutions={resolutions} locked={phase !== 'review'} onResolve={(id, r) => setResolutions((all) => ({ ...all, [id]: r }))}
        rippleActions={rippleActions} onRipple={(id, a) => setRippleActions((all) => ({ ...all, [id]: a }))}
        onEdit={(text) => edit.mutate(text)} editing={edit.isPending} changes={changes} editError={edit.error ? errorMessage(edit.error) : null} />
    </div>}

    {/* 4 · Approved: the seal, then the workspace opens up. */}
    {(phase === 'approved' || phase === 'rejected') && <section className="done" ref={doneRef}>
      <Seal tone={phase === 'approved' ? 'accent' : 'muted'} />
      <motion.h2 initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={{ delay: 0.7, duration: 0.9, ease: EASE }}>
        {phase === 'approved' ? <>Approved.<br /><span>Your team remembers.</span></> : <>Set aside.<br /><span>Nothing was changed.</span></>}
      </motion.h2>
      {phase === 'approved' && <>
        {outcome && outcome.created_tasks.length + outcome.superseded_ids.length + outcome.heads_up_sent.length > 0 && <motion.div className="done-stats" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1, duration: 0.8, ease: EASE }}>
          <div><b><CountUp to={outcome.created_tasks.length} /></b><span>tasks on the board</span></div>
          <div><b><CountUp to={outcome.superseded_ids.length} /></b><span>old decisions retired</span></div>
          <div><b><CountUp to={outcome.heads_up_sent.length} /></b><span>heads-ups sent</span></div>
        </motion.div>}
        <Appear delay={1.2} className="done-actions">
          <Link className="run-btn" to="/board">Open the team board<ArrowUpRight size={16} /></Link>
          <Link className="ghost-btn" to="/memory">See decision memory</Link>
          <button type="button" className="link-btn" onClick={startOver}>Capture another meeting</button>
        </Appear>
      </>}
      {phase === 'rejected' && <Appear delay={1} className="done-actions"><button type="button" className="run-btn" onClick={startOver}>Capture another meeting<ArrowRight size={16} /></button></Appear>}
    </section>}

    {/* The approve bar: the only way anything leaves. */}
    <AnimatePresence>{phase === 'review' && review && <motion.div className="approve-bar" key="bar"
      initial={{ y: 120, opacity: 0 }} animate={{ y: 0, opacity: 1, transition: { delay: 1, duration: 0.8, ease: EASE } }}
      exit={{ y: 120, opacity: 0, transition: { duration: 0.4, ease: EASE_IN_OUT } }}>
      <div className="approve-copy">
        <span className="approve-dots">{conflictIds.map((id) => <i key={id} className={resolutions[id] ? 'on' : ''} />)}</span>
        <div><strong>{!conflictIds.length ? 'No conflicts with memory.' : ready ? 'All conflicts decided.' : `${conflictIds.length - decided} conflict${conflictIds.length - decided > 1 ? 's' : ''} need your call`}</strong>
          <span>{issue ?? 'Nothing is saved or sent until you approve.'}</span></div>
      </div>
      <div className="approve-actions">
        {!ready && <button type="button" className="link-btn" onClick={() => setResolutions(Object.fromEntries(conflictIds.map((id) => [id, 'accept_new' as const])))}><CheckCheck size={15} />Accept all new</button>}
        <button type="button" className="ghost-btn" disabled={reject.isPending || approve.isPending} onClick={() => reject.mutate()}>Reject</button>
        <button type="button" className="run-btn" disabled={!ready || approve.isPending || reject.isPending} onClick={() => approve.mutate()}>
          {approve.isPending ? <><LoaderCircle size={16} className="spin" />Approving…</> : <>Approve<ArrowRight size={16} /></>}</button>
      </div>
    </motion.div>}</AnimatePresence>
  </div>
}
