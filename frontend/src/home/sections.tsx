import { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { ArrowRight, AudioLines, Check, CircleAlert, GitFork, LoaderCircle, Quote, Send, Sparkles, Waves } from 'lucide-react'
import { Avatar } from '@/components/shared'
import type { AgentEvent, AgentName, Conflict, Decision, Resolution, ReviewPayload, Ripple, Task } from '@/types'
import { markTranscript, shortDate, topicLabel } from './marks'
import { Appear, CountUp, RiseOnView, Strike, Typewriter } from './motion'
import { EASE, type STEPS } from './constants'

export type Seen = AgentEvent & { seen: number }

const friendly = (message: string) => message.startsWith('Not built yet') ? 'Skipped for now' : message

/** The live agent pipeline: nodes light up in turn while a track fills behind them. */
export function Pipeline({ events, steps }: { events: Seen[]; steps: typeof STEPS }) {
  const state = (agent: AgentName) => {
    const own = events.filter((e) => e.agent === agent)
    return { done: own.some((e) => e.type === 'agent_end'), active: own.length > 0, last: own.at(-1) }
  }
  const doneCount = steps.filter((s) => state(s.agent).done).length
  const activeIndex = steps.findIndex((s) => !state(s.agent).done)
  const progress = steps.length > 1 ? Math.min(1, (doneCount === steps.length ? steps.length - 1 : Math.max(0, activeIndex)) / (steps.length - 1)) : 1
  return <div className="pipeline" style={{ ['--steps' as string]: steps.length }}>
    <div className="pipeline-track" aria-hidden>
      <motion.div className="pipeline-fill" initial={{ scaleX: 0 }} animate={{ scaleX: progress }} transition={{ duration: 0.9, ease: EASE }} />
    </div>
    {steps.map((step, i) => {
      const s = state(step.agent)
      const status = s.done ? 'done' : s.active ? 'active' : 'waiting'
      return <motion.div key={step.agent} className={`node is-${status}`} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 + i * 0.08, duration: 0.7, ease: EASE }}>
        <span className="node-dot">
          {s.done ? <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 20 }}><Check size={17} strokeWidth={2.6} /></motion.span>
            : <span className="node-num">{String(i + 1).padStart(2, '0')}</span>}
          {status === 'active' && <span className="node-pulse" />}
        </span>
        <strong>{step.label}</strong>
        <p>{s.last && s.last.type !== 'agent_start' ? <Typewriter key={s.last.message} text={friendly(s.last.message)} />
          : s.active ? <Typewriter key={s.last?.message} text={s.last?.message ?? ''} /> : step.idle}</p>
      </motion.div>
    })}
  </div>
}

function Stats({ review }: { review: ReviewPayload }) {
  const cleaned = review.corrections.reduce((n, c) => n + (c.kind === 'filler' ? c.original.split(',').length : 1), 0)
  const stats = [
    { label: 'Decisions', n: review.decisions.length },
    { label: 'Tasks with owners', n: review.tasks.length },
    { label: 'Conflicts with memory', n: review.conflicts.length, hot: review.conflicts.length > 0 },
    { label: 'Words cleaned up', n: cleaned },
  ]
  return <div className="stats">{stats.map((s, i) => <Appear key={s.label} delay={i * 0.07} className={`stat ${s.hot ? 'is-hot' : ''}`}>
    <span className="stat-n"><CountUp to={s.n} /></span><span className="stat-label">{s.label}</span>
  </Appear>)}</div>
}

const findNew = (r: ReviewPayload, id: string): Decision | Task | undefined => r.decisions.find((d) => d.id === id) ?? r.tasks.find((t) => t.id === id)

function Collision({ conflict, review, index, resolution, onResolve, locked }: {
  conflict: Conflict; review: ReviewPayload; index: number; resolution?: Resolution; onResolve: (r: Resolution) => void; locked: boolean
}) {
  const fresh = findNew(review, conflict.new_item_id)
  const old = conflict.old_decision
  const kept = resolution === 'keep_old'
  const accepted = resolution === 'accept_new'
  const label = conflict.severity === 'high' ? 'Direction changed' : conflict.severity === 'medium' ? 'Timeline changed' : 'Worth a look'
  return <Appear delay={index * 0.08} className={`collision sev-${conflict.severity} ${kept ? 'is-kept' : ''} ${accepted ? 'is-accepted' : ''}`}>
    <div className="collision-head">
      <span className="sev-pill"><CircleAlert size={13} />{label}</span>
      <span className="collision-type">{conflict.type.replace('_', ' ')}</span>
    </div>
    {old ? <div className="versus">
      <div className="side side-old">
        <span className="side-label">What you agreed · {shortDate(old.date)}</span>
        <p className="side-text"><Strike off={kept}>{old.statement}</Strike></p>
        <span className="side-by"><Avatar name={old.made_by} small />{old.made_by}</span>
      </div>
      <motion.span className="versus-arrow" initial={{ scale: 0, rotate: -120 }} whileInView={{ scale: 1, rotate: 0 }} viewport={{ once: true, amount: 0.8 }}
        transition={{ type: 'spring', stiffness: 260, damping: 18, delay: 0.55 }}><ArrowRight size={18} /></motion.span>
      <div className="side side-new">
        <span className="side-label">What you just said · {shortDate(review.meeting.date)}</span>
        <p className="side-text">{fresh ? <RiseOnView delay={0.6}>{'statement' in fresh ? fresh.statement : fresh.title}</RiseOnView> : conflict.explanation}</p>
        {fresh && 'made_by' in fresh && <span className="side-by"><Avatar name={fresh.made_by} small />{fresh.made_by}</span>}
      </div>
    </div> : <p className="notice-text">{conflict.explanation}</p>}
    {old && <p className="collision-why"><Sparkles size={14} />{conflict.explanation}</p>}
    <div className="collision-foot">
      {conflict.affected_tasks.length > 0 && <div className="affected"><span><GitFork size={13} />Work already underway</span>
        {conflict.affected_tasks.map((t) => <span className="chip" key={t.id}>{t.title}<em>{t.owner}{t.due_date ? ` · ${shortDate(t.due_date)}` : ''}</em></span>)}
      </div>}
      {old && <div className="segmented-choice" role="group" aria-label="Resolve this conflict">
        <button type="button" disabled={locked} aria-pressed={kept} className={kept ? 'on' : ''} onClick={() => onResolve('keep_old')}>Keep previous</button>
        <button type="button" disabled={locked} aria-pressed={accepted} className={accepted ? 'on accept' : ''} onClick={() => onResolve('accept_new')}>
          {accepted && <Check size={14} />}Accept new</button>
        <motion.span className="segmented-thumb" initial={false} transition={{ type: 'spring', stiffness: 500, damping: 36 }}
          animate={{ left: accepted ? '50%' : '0%', opacity: resolution ? 1 : 0 }} />
      </div>}
    </div>
  </Appear>
}

function Transcript({ review }: { review: ReviewPayload }) {
  return <p className="transcript">{markTranscript(review.raw_text, review.corrections).map((s, i) => {
    if (!s.mark) return <span key={i}>{s.text}</span>
    switch (s.mark.kind) {
      case 'filler': return <s className="mk-filler" key={i}>{s.text}</s>
      case 'digression': return <span className="mk-cut" key={i}><s>{s.text}</s><span className="mk-tag">off-topic</span></span>
      case 'self_correction': return <span className="mk-fix" key={i}><s>{s.text}</s><span className="mk-tag">{shortDate(s.mark.resolved)}</span></span>
      case 'date_resolution': return <span className="mk-date" key={i}>{s.text}<span className="mk-tag soft">{shortDate(s.mark.resolved)}</span></span>
    }
  })}</p>
}

const RIPPLE_WORD: Record<Ripple['kind'], string> = { reschedule: 'Move date', rescope: 'Rescope', cancel: 'Cancel', unowned_work: 'Needs an owner' }
/** Suggestions built from this review's own tasks, so they always refer to something that exists. */
function examplesFor(tasks: { title: string; owner: string | null }[]): string[] {
  const first = tasks[0]
  const second = tasks[1] ?? tasks[0]
  const out: string[] = []
  if (first) out.push(`Make “${first.title}” due on the 18th`)
  if (second && second !== first) out.push(`Drop “${second.title}”`)
  else if (first) out.push(`Drop “${first.title}”`)
  if (first) out.push(`Assign “${first.title}” to ${first.owner === 'Ananya' ? 'Priya' : 'Ananya'}`)
  return out
}


function RippleRow({ ripple, on, disabled, onToggle }: { ripple: Ripple; on: boolean; disabled: boolean; onToggle: (apply: boolean) => void }) {
  const p = ripple.proposal
  return <label className={`ripple-row ${disabled ? 'is-off' : ''} ${on ? 'is-on' : ''}`}>
    <input type="checkbox" checked={on && !disabled} disabled={disabled} onChange={(e) => onToggle(e.target.checked)} />
    <span className="ripple-check"><Check size={13} strokeWidth={3} /></span>
    <span className="ripple-kind">{RIPPLE_WORD[ripple.kind]}</span>
    <div className="ripple-body">
      <strong>{ripple.task?.title ?? 'New work with no owner'}</strong>
      <p>{disabled ? 'You kept the previous decision, so this will be skipped.' : ripple.reason}</p>
      {!disabled && (p.due_date || p.title) && <span className="ripple-to"><ArrowRight size={12} />{p.due_date && ripple.task?.due_date ? `${shortDate(ripple.task.due_date)} → ${shortDate(p.due_date)}` : p.title}</span>}
    </div>
    {ripple.task?.owner && <Avatar name={ripple.task.owner} small />}
  </label>
}

function VoiceEdit({ onEdit, editing, changes, error, examples }: { onEdit: (text: string) => void; editing: boolean; changes: string[]; error: string | null; examples: string[] }) {
  const [text, setText] = useState('')
  const send = (value: string) => { if (value.trim() && !editing) { onEdit(value.trim()); setText('') } }
  return <section className="block voice-edit">
    <div className="block-head"><h2><RiseOnView>Change anything, just say it.</RiseOnView></h2>
      <p>Hold Wispr and tell Quorum what to fix. It edits the review and shows you exactly what changed.</p></div>
    <Appear className="edit-card">
      <form onSubmit={(e) => { e.preventDefault(); send(text) }}>
        <span className="edit-icon"><AudioLines size={18} /></span>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="“Move the beta testers message to Tuesday”" aria-label="Tell Quorum what to change" />
        <button type="submit" className="run-btn small" disabled={!text.trim() || editing}>{editing ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}Apply</button>
      </form>
      <div className="edit-examples">{examples.map((e) => <button type="button" key={e} onClick={() => send(e)} disabled={editing}>{e}</button>)}</div>
      {error && <p className="error-line" role="alert">{error}</p>}
      {changes.length > 0 && <motion.ul className="edit-changes" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
        {changes.map((c, i) => <li key={i}><Check size={14} />{c}</li>)}</motion.ul>}
    </Appear>
  </section>
}

export function Results({ review, resolutions, onResolve, locked, rippleActions, onRipple, onEdit, editing, changes, editError }: {
  review: ReviewPayload; resolutions: Record<string, Resolution>; onResolve: (id: string, r: Resolution) => void; locked: boolean
  rippleActions: Record<string, 'apply' | 'skip'>; onRipple: (id: string, action: 'apply' | 'skip') => void
  onEdit: (text: string) => void; editing: boolean; changes: string[]; editError: string | null
}) {
  return <div className="results">
    <Stats review={review} />

    {review.conflicts.length > 0 && <section className="block">
      <div className="block-head">
        <h2><RiseOnView>This contradicts what your team agreed.</RiseOnView></h2>
        <p>Quorum checked every new decision against memory. You decide what carries forward.</p>
      </div>
      <div className="collisions">{review.conflicts.map((c, i) => <Collision key={c.id} conflict={c} review={review} index={i} locked={locked}
        resolution={resolutions[c.id]} onResolve={(r) => onResolve(c.id, r)} />)}</div>
    </section>}

    {review.ripples.length > 0 && <section className="block ripple">
      <div className="block-head"><h2><RiseOnView>And here’s what that changes.</RiseOnView></h2>
        <p>Quorum traced each change into work already underway. Switch off anything you don’t want applied.</p></div>
      <Appear className="card ripple-card">
        {review.ripples.map((r) => {
          const off = Boolean(r.conflict_id && resolutions[r.conflict_id] === 'keep_old')
          return <RippleRow key={r.id} ripple={r} disabled={off || locked} on={(rippleActions[r.id] ?? r.default_action) === 'apply'}
            onToggle={(apply) => onRipple(r.id, apply ? 'apply' : 'skip')} />
        })}
      </Appear>
      {review.heads_up.length > 0 && <div className="heads-up">
        <span className="card-label"><Waves size={13} />Heads-ups ready to send <b>{review.heads_up.length}</b></span>
        <div className="heads-grid">{review.heads_up.map((h, i) => <Appear key={h.person} delay={i * 0.08} className="card note">
          <span className="side-by"><Avatar name={h.person} small />{h.person}</span><ReactMarkdown>{h.message_md}</ReactMarkdown></Appear>)}</div>
      </div>}
    </section>}

    <section className="block forward">
      <div className="block-head"><h2><RiseOnView>What you’re taking forward.</RiseOnView></h2></div>
      <div className="forward-grid">
        <Appear className="card">
          <span className="card-label">Decisions <b>{review.decisions.length}</b></span>
          {review.decisions.map((d) => <div className="decision" key={d.id}>
            <span className="topic">{topicLabel(d.topic_key)}</span>
            <strong>{d.statement}</strong>
            <span className="side-by"><Avatar name={d.made_by} small />Called by {d.made_by}</span>
            {d.source_quote && <span className="quote"><Quote size={12} />{d.source_quote}</span>}
          </div>)}
          {!review.decisions.length && <p className="muted-line">No decisions in this debrief.</p>}
        </Appear>
        <Appear className="card" delay={0.08}>
          <span className="card-label">Tasks <b>{review.tasks.length}</b></span>
          {review.tasks.map((t) => <div className="task" key={t.id}>
            <span className="task-ring" />
            <div><strong>{t.title}</strong>
              <span className="task-meta"><Avatar name={t.owner || '?'} small />{t.owner || 'Unassigned'}
                <span className="due">{t.due_date ? shortDate(t.due_date) : 'No date'}</span>
                {t.raw_due_phrase && <em>you said “{t.raw_due_phrase}”</em>}</span>
            </div>
          </div>)}
          {review.questions.map((q) => <p className="question" key={q.id}><CircleAlert size={13} />{q.prompt}</p>)}
          {!review.tasks.length && <p className="muted-line">No tasks in this debrief.</p>}
        </Appear>
        <Appear className="card card-wide" delay={0.16}>
          <span className="card-label">Your words, cleaned up</span>
          <Transcript review={review} />
          <span className="legend"><s>struck</s> trimmed · <span className="mk-tag">tag</span> Quorum’s fix · your original words are always kept</span>
        </Appear>
      </div>
    </section>

    {!locked && <VoiceEdit onEdit={onEdit} editing={editing} changes={changes} error={editError} examples={examplesFor(review.tasks)} />}
  </div>
}
