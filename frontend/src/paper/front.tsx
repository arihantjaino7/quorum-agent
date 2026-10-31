import { useRef, type ReactNode } from 'react'
import { motion, useInView } from 'framer-motion'
import type { Conflict, Decision, Resolution, ReviewPayload, Task } from '@/types'
import { Appear, Band, CountUp, RiseOnView, Rule } from './parts'
import { longDate, markTranscript, shortDate, topicLabel } from './marks'

const TYPE_WORD: Record<Conflict['type'], string> = {
  reversal: 'Reversal', contradiction: 'Contradiction', deadline_collision: 'Deadline clash', overload: 'Overload',
}
const SEVERITY_WORD: Record<Conflict['severity'], string> = { high: 'High', medium: 'Medium', low: 'Low' }

function findNew(review: ReviewPayload, id: string): Decision | Task | undefined {
  return review.decisions.find((d) => d.id === id) ?? review.tasks.find((t) => t.id === id)
}
const headline = (item: Decision | Task | undefined) => !item ? '' : 'statement' in item ? item.statement : item.title

function Stats({ review }: { review: ReviewPayload }) {
  const edits = review.corrections.reduce((n, c) => n + (c.kind === 'filler' ? c.original.split(',').length : 1), 0)
  const stats = [
    ['Decisions', review.decisions.length], ['Assignments', review.tasks.length],
    ['Corrections to the record', review.conflicts.length], ['Edits to your words', edits],
  ] as const
  return <div className="stats">
    {stats.map(([label, n], i) => <Appear className="stat" key={label} delay={i * 0.08}>
      <span className="stat-label">{label}</span><span className="stat-n"><CountUp to={n} /></span>
    </Appear>)}
  </div>
}

/** Red-ink strike that draws across the old headline, line by line, once it is read. */
function Strike({ children, off }: { children: ReactNode; off: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  const seen = useInView(ref, { once: true, amount: 0.9 })
  return <motion.span ref={ref} className="strike" initial={{ backgroundSize: '0% 0.09em' }}
    animate={{ backgroundSize: seen && !off ? '100% 0.09em' : '0% 0.09em' }}
    transition={{ duration: 0.9, delay: off ? 0 : 0.35, ease: [0.76, 0, 0.24, 1] }}>{children}</motion.span>
}

function CorrectionBox({ conflict, review, index, resolution, onResolve, locked }: {
  conflict: Conflict; review: ReviewPayload; index: number; resolution?: Resolution
  onResolve: (r: Resolution) => void; locked: boolean
}) {
  const fresh = findNew(review, conflict.new_item_id)
  const old = conflict.old_decision
  const kept = resolution === 'keep_old'
  return <Appear className={`correction ${index === 0 ? 'correction-lead' : ''} sev-${conflict.severity}`} delay={index * 0.1}>
    <div className="correction-kicker">
      <span className="correction-tag">{old ? 'Correction' : 'Notice'}</span>
      <span>{TYPE_WORD[conflict.type]} · {SEVERITY_WORD[conflict.severity]}</span>
    </div>
    {old && <h3 className="correction-old"><Strike off={kept}>{old.statement}</Strike></h3>}
    {old && <p className="correction-meta">As decided {shortDate(old.date)} by {old.made_by}</p>}
    <h3 className={`correction-new ${kept ? 'is-kept' : ''}`}>{fresh ? <RiseOnView delay={0.5}>{headline(fresh)}</RiseOnView> : conflict.explanation}</h3>
    {fresh && 'made_by' in fresh && <p className="correction-meta">Now, per {fresh.made_by} · {review.meeting.title}</p>}
    {fresh && <p className="correction-body dropcap">{conflict.explanation}</p>}
    {!!conflict.affected_tasks.length && <div className="correction-risk">
      <span className="small-caps">Work already underway</span>
      <ul>{conflict.affected_tasks.map((t) => <li key={t.id}>{t.title} <em>· {t.owner}{t.due_date ? `, due ${shortDate(t.due_date)}` : ''}</em></li>)}</ul>
    </div>}
    {old && <div className="choice" role="group" aria-label={`Resolve: ${old.statement}`}>
      <button type="button" disabled={locked} aria-pressed={resolution === 'accept_new'} className={resolution === 'accept_new' ? 'on' : ''}
        onClick={() => onResolve('accept_new')}>{resolution === 'accept_new' ? '✓ ' : ''}Accept the new call</button>
      <button type="button" disabled={locked} aria-pressed={kept} className={kept ? 'on' : ''}
        onClick={() => onResolve('keep_old')}>{kept ? '✓ ' : ''}Keep the old one</button>
    </div>}
  </Appear>
}

function Transcript({ review }: { review: ReviewPayload }) {
  const segments = markTranscript(review.raw_text, review.corrections)
  return <p className="transcript">{segments.map((s, i) => {
    if (!s.mark) return <span key={i}>{s.text}</span>
    switch (s.mark.kind) {
      case 'filler': return <s className="mk-filler" key={i} title="Filler removed">{s.text}</s>
      case 'digression': return <span className="mk-cut" key={i} title="Off-topic: cut"><s>{s.text}</s><span className="mk-note">cut</span></span>
      case 'self_correction': return <span className="mk-fix" key={i}><s>{s.text}</s><span className="mk-note">{shortDate(s.mark.resolved)}</span></span>
      case 'date_resolution': return <span className="mk-date" key={i} title={s.mark.resolved}>{s.text}<sup>{shortDate(s.mark.resolved)}</sup></span>
    }
  })}</p>
}

export function FrontPage({ review, resolutions, onResolve, locked }: {
  review: ReviewPayload; resolutions: Record<string, Resolution>; onResolve: (id: string, r: Resolution) => void; locked: boolean
}) {
  const { meeting } = review
  return <article className="front" aria-label="Your debrief, as a front page">
    <div className="dateline">
      <span>{meeting.title}</span><span>Filed by {meeting.speaker}</span><span>{longDate(meeting.date)}</span>
    </div>
    <Rule double />
    <Stats review={review} />
    <Rule />

    {!!review.conflicts.length && <section className="front-section">
      <Band kicker="Checked against memory">
        {review.conflicts.length} correction{review.conflicts.length > 1 ? 's' : ''} to the record
      </Band>
      <div className="corrections">
        {review.conflicts.map((c, i) => <CorrectionBox key={c.id} conflict={c} review={review} index={i} locked={locked}
          resolution={resolutions[c.id]} onResolve={(r) => onResolve(c.id, r)} />)}
      </div>
    </section>}

    <section className="front-section columns">
      <div className="col col-decisions">
        <h2 className="col-head"><RiseOnView>The decisions</RiseOnView></h2>
        {review.decisions.map((d, i) => <Appear key={d.id} className="story" delay={i * 0.08}>
          <span className="small-caps">{topicLabel(d.topic_key)}</span>
          <h3 className="story-head">{d.statement}</h3>
          <p className="byline">Called by {d.made_by}</p>
          {d.source_quote && <blockquote className="pull">“{d.source_quote}”</blockquote>}
        </Appear>)}
        {!review.decisions.length && <p className="quiet">No decisions in this debrief.</p>}
      </div>
      <Rule vertical className="col-rule" />
      <div className="col col-tasks">
        <h2 className="col-head"><RiseOnView>Assignments</RiseOnView></h2>
        <ol className="assignments">{review.tasks.map((t, i) => <Appear key={t.id} delay={i * 0.08}><li>
          <span className="owner">{t.owner || 'Unassigned'}</span>
          <span className="task-title">{t.title}</span>
          <span className="due">{t.due_date ? `Due ${shortDate(t.due_date)}` : 'No date yet'}{t.raw_due_phrase && <em> · said “{t.raw_due_phrase}”</em>}</span>
        </li></Appear>)}</ol>
        {!review.tasks.length && <p className="quiet">No assignments in this debrief.</p>}
        {!!review.questions.length && <div className="wanted"><span className="small-caps">Still wanted</span>
          {review.questions.map((q) => <p key={q.id}>{q.prompt}</p>)}</div>}
      </div>
      <Rule vertical className="col-rule" />
      <div className="col col-transcript">
        <h2 className="col-head"><RiseOnView>As you said it</RiseOnView></h2>
        <p className="small-caps legend"><s>struck</s> = trimmed · <span className="legend-red">red</span> = the editor’s fix</p>
        <Transcript review={review} />
      </div>
    </section>
  </article>
}
