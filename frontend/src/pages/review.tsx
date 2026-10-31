import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { ArrowDown, ArrowRight, ArrowUpRight, AudioLines, Check, CheckCheck, ChevronRight, CircleAlert, FileText, GitCompareArrows, GitFork, LoaderCircle, MessageSquare, Send, ShieldCheck, X } from 'lucide-react'
import { api, ApiError, useMocks } from '@/api'
import { Avatar, Empty, ErrorState, Loading, PageHeading, SourceLink } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useApp } from '@/lib/app-context'
import { errorMessage, formatDate } from '@/lib/utils'
import type { ApproveResult, Correction, Resolution } from '@/types'

const topicLabel = (key: string) => ({ platform_scope: 'Platform scope', launch_date: 'Launch date', payments_provider: 'Payments' })[key] ?? key.replaceAll('_', ' ')

function CorrectedText({ text, corrections }: { text: string; corrections: Correction[] }) {
  const correctionsByValue = new Map(corrections.filter((c) => c.resolved).map((c) => [c.resolved, c]))
  const values = [...correctionsByValue.keys()].sort((a, b) => b.length - a.length)
  const pattern = values.length ? new RegExp(`(${values.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g') : null
  return <div className="clean-prose">{text.split('\n\n').map((paragraph, index) => <p key={index}>{(pattern ? paragraph.split(pattern) : [paragraph]).map((part, j) => {
    const correction = correctionsByValue.get(part)
    return correction ? <button type="button" className="correction-mark" key={j} title={`Originally: ${correction.original}`} aria-label={`${part}. Originally: ${correction.original}`}>{part}<span>↗</span></button> : part
  })}</p>)}</div>
}

export default function Review() {
  const { threadId = '' } = useParams()
  const { notify } = useApp()
  const client = useQueryClient()
  const navigate = useNavigate()
  const [activeConflict, setActiveConflict] = useState(0)
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>({})
  const [rippleActions, setRippleActions] = useState<Record<string, 'apply' | 'skip'>>({})
  const [instruction, setInstruction] = useState('')
  const [changes, setChanges] = useState<string[]>([])
  const [showRaw, setShowRaw] = useState(false)
  const [outcome, setOutcome] = useState<ApproveResult | 'rejected' | null>(null)
  const [rejectionOpen, setRejectionOpen] = useState(false)
  const review = useQuery({ queryKey: ['quorum', 'review', threadId], queryFn: () => api.getReview(threadId), retry: false })
  const edit = useMutation({ mutationFn: (value: string) => api.voiceEdit(threadId, value), onSuccess: (result) => {
    client.setQueryData(['quorum', 'review', threadId], result.review); setChanges(result.changes); setInstruction('')
  } })
  const approve = useMutation({ mutationFn: () => api.approve(threadId, { resolutions, ripple_actions: rippleActions }), onSuccess: (result) => {
    setOutcome(result); void client.invalidateQueries({ queryKey: ['quorum'] }); notify('Decisions confirmed. Your team’s memory is up to date.')
  } })
  const reject = useMutation({ mutationFn: () => api.reject(threadId), onSuccess: () => { setOutcome('rejected'); void client.invalidateQueries({ queryKey: ['quorum'] }) } })
  const retryExecution = useMutation({ mutationFn: () => api.retryRun(threadId), onSuccess: () => navigate(`/runs/${encodeURIComponent(threadId)}?resuming=1`) })
  if (outcome) return <>
    <PageHeading number="02" eyebrow={outcome === 'rejected' ? 'YOUR CALL, ALWAYS' : 'FROM CONVERSATION TO COMMITMENT'} title={outcome === 'rejected' ? 'Set aside.' : 'Everyone, on the same page.'} soft={outcome === 'rejected' ? 'A fresh start is a word away.' : 'And ready for what’s next.'} description={outcome === 'rejected' ? 'This debrief was rejected. No tasks or decisions were changed.' : 'The decisions are remembered, the work is lined up, and each commitment has a place to go.'} />
    {outcome !== 'rejected' && <Card className="approval-result"><span className="approval-seal"><ShieldCheck size={34} strokeWidth={1.5} /></span><h2>Consider it remembered.</h2><div className="result-stats"><div><b>{outcome.created_tasks.length}</b><span>tasks created</span></div><div><b>{outcome.superseded_ids.length}</b><span>decisions superseded</span></div><div><b>{outcome.updated_tasks.length + outcome.cancelled_task_ids.length}</b><span>existing tasks updated</span></div></div><p>{useMocks ? 'Demo actions are saved locally. No Notion pages or Telegram messages were sent.' : `${outcome.heads_up_sent.length} personal heads-up notes processed. See the team board for tracker links.`}</p><div className="button-row"><Button asChild><Link to="/board">See the team board<ArrowRight size={15} /></Link></Button><Button asChild variant="outline"><Link to="/memory">Follow the decision history<GitFork size={14} /></Link></Button></div></Card>}
    <Button asChild variant="ghost"><Link to="/capture">Capture another meeting<ArrowRight size={14} /></Link></Button>
  </>
  if (review.isPending) return <Loading label="Opening the conversation…" />
  if (review.error) return <><ErrorState error={review.error} retry={() => void review.refetch()} /><Button asChild variant="outline"><Link to="/capture">Start a meeting debrief<ArrowRight size={14} /></Link></Button></>
  const value = review.data
  if (!value) return <Empty title="No review waiting here.">Start with a meeting debrief and we’ll get everything ready.</Empty>
  const conflict = value.conflicts[activeConflict] ?? value.conflicts[0]
  const newItem = conflict ? [...value.decisions, ...value.tasks].find((d) => d.id === conflict.new_item_id) : null
  const unanswered = value.questions.length
  const unresolved = value.conflicts.filter((c) => !resolutions[c.id]).length
  const executionFailed = approve.error instanceof ApiError && approve.error.status === 502
  const busy = edit.isPending || approve.isPending || reject.isPending || executionFailed
  function setResolution(id: string, resolution: Resolution) {
    setResolutions((all) => ({ ...all, [id]: resolution }))
  }
  function fieldEdit(title: string, field: string, next: string, previous: string | null) {
    if (next && next !== previous) edit.mutate(`Set task "${title}" ${field} to "${next}"`)
  }
  return <>
    <PageHeading number="02" eyebrow="THE MOST IMPORTANT AGENT IS YOU" title="A few things changed." soft="Let’s make sure they should." description="Your debrief, connected to everything your team already agreed. Take a look before words become work." />
    <div className="review-meeting-meta"><span className="meeting-type"><AudioLines size={14} />{value.meeting.title}</span><span>{formatDate(value.meeting.date, { year: 'numeric' })}</span><span className="with-avatar"><Avatar name={value.meeting.speaker} small />{value.meeting.speaker}</span><span className="tag review-ready-tag"><Check size={11} />Ready for review</span></div>
    <div className="mini-pipeline" aria-label="Completed agent pipeline">{['Normalized', 'Extracted', 'Memory checked', 'Conflicts surfaced'].map((label) => <span key={label}><Check size={11} />{label}<ChevronRight size={12} /></span>)}<strong><span className="status-dot" />Your review</strong></div>
    {conflict && <motion.section className="conflict-section" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
      <div className="section-heading"><h2><GitCompareArrows size={20} />A change of direction<span className="conflict-count">{value.conflicts.length}</span></h2><button className="text-button" onClick={() => setResolutions(Object.fromEntries(value.conflicts.map((c) => [c.id, 'accept_new'])))}><CheckCheck size={14} />Accept all new decisions</button></div>
      <p className="section-intro">These decisions disagree with your team’s memory. You decide what carries forward.</p>
      <div className="conflict-tabs" role="tablist" aria-label="Meeting conflicts">{value.conflicts.map((item, index) => {
        const decision = value.decisions.find((d) => d.id === item.new_item_id)
        return <button key={item.id} role="tab" id={`conflict-tab-${index}`} aria-selected={index === activeConflict} aria-controls="conflict-detail" className={index === activeConflict ? 'active' : ''} onClick={() => setActiveConflict(index)}><span className={`conflict-tab-icon ${resolutions[item.id] ? 'resolved' : ''}`}>{resolutions[item.id] ? <Check size={13} /> : String(index + 1).padStart(2, '0')}</span><strong>{decision ? topicLabel(decision.topic_key) : 'Task conflict'}</strong><span className="tab-outcome">{resolutions[item.id] ? resolutions[item.id] === 'accept_new' ? 'New accepted' : 'Previous kept' : 'Needs your call'}</span></button>
      })}</div>
      <AnimatePresence mode="wait"><motion.div key={conflict.id} id="conflict-detail" role="tabpanel" aria-labelledby={`conflict-tab-${activeConflict}`} className="conflict-detail" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}>
        <div className="conflict-detail-head"><span className={`severity severity-${conflict.severity}`}><CircleAlert size={12} />{conflict.severity === 'high' ? 'Direction changed' : 'Timeline changed'}</span><span className="tiny-label">{conflict.type.replaceAll('_', ' ')}</span></div>
        <div className="decision-compare"><div className="previous-decision"><span className="tiny-label">WHAT WE AGREED</span><h3>{conflict.old_decision?.statement ?? 'Existing task commitments'}</h3>{conflict.old_decision && <SourceLink meetingId={conflict.old_decision.meeting_id} title="Earlier meeting" date={conflict.old_decision.date} />}</div><span className="compare-arrow"><ArrowRight size={20} /></span><div className="proposed-decision"><span className="tiny-label">WHAT YOU JUST SAID</span><h3>{newItem && ('statement' in newItem ? newItem.statement : newItem.title)}</h3><span className="new-decision-caption">{value.meeting.title} · {formatDate(value.meeting.date)}</span></div></div>
        <p className="conflict-explanation">{conflict.explanation}</p>
        <div className="conflict-detail-foot"><span><GitFork size={13} />{conflict.affected_tasks.length} existing task{conflict.affected_tasks.length !== 1 ? 's' : ''} affected</span><div className="resolution-control" aria-label="Resolve this conflict"><button aria-pressed={resolutions[conflict.id] === 'keep_old'} className={resolutions[conflict.id] === 'keep_old' ? 'chosen' : ''} onClick={() => setResolution(conflict.id, 'keep_old')}>{resolutions[conflict.id] === 'keep_old' && <Check size={12} />}Keep previous</button><button aria-pressed={resolutions[conflict.id] === 'accept_new'} className={`accept-resolution ${resolutions[conflict.id] === 'accept_new' ? 'chosen' : ''}`} onClick={() => setResolution(conflict.id, 'accept_new')}>{resolutions[conflict.id] === 'accept_new' ? <Check size={12} /> : <ArrowRight size={12} />}Accept new decision</button></div></div>
      </motion.div></AnimatePresence>
    </motion.section>}
    <div className="review-columns">
      <section className="debrief-review"><div className="section-heading"><h2><FileText size={17} />The conversation, clearer.</h2><div className="segmented compact"><button className={!showRaw ? 'selected' : ''} aria-pressed={!showRaw} onClick={() => setShowRaw(false)}>Cleaned</button><button className={showRaw ? 'selected' : ''} aria-pressed={showRaw} onClick={() => setShowRaw(true)}>Original</button></div></div><Card className="cleaned-card"><div className="document-meta"><AudioLines size={13} />{value.meeting.source_type === 'voice' ? 'VOICE DEBRIEF' : 'TRANSCRIPT'}<span>{value.corrections.length} thoughtful corrections</span></div>{showRaw ? <div className="clean-prose raw-prose"><p>{value.raw_text}</p></div> : <CorrectedText text={value.clean_text} corrections={value.corrections} />}<div className="correction-legend"><span><span className="legend-dash" />Hover or focus highlighted words to see the original.</span>{value.corrections.filter((c) => !c.resolved).map((c, index) => <details key={index}><summary>{c.kind === 'digression' ? 'Digression removed' : 'Filler removed'}<ChevronDownIcon /></summary><p>“{c.original}”</p></details>)}</div></Card>
        <div className="memory-assurance"><ShieldCheck size={17} /><p>Cleaned for clarity.<br /><strong>Your original words are always kept.</strong></p></div>
      </section>
      <section className="extracted-review"><div className="section-heading"><h2><CheckCheck size={18} />What we’re taking forward.</h2><span className="tag">{value.decisions.length + value.tasks.length} items</span></div><div className="subsection-label">DECISIONS <span>{value.decisions.length}</span></div>
        {value.decisions.map((decision) => <Card className="decision-edit-card" key={decision.id}><div><span className="decision-small-icon"><GitFork size={14} /></span><label><span className="tiny-label">{topicLabel(decision.topic_key)}</span><input aria-label={`Edit ${topicLabel(decision.topic_key)} decision`} key={decision.statement} defaultValue={decision.statement} disabled={busy} onBlur={(e) => { if (e.target.value.trim() && e.target.value !== decision.statement) edit.mutate(`Change decision "${decision.statement}" to "${e.target.value.trim()}"`) }} /></label></div><span className="decision-attribution">{decision.made_by} · This meeting</span></Card>)}
        <div className="subsection-label task-subsection">COMMITMENTS <span>{value.tasks.length}</span></div>
        {value.tasks.map((task) => <Card className="task-edit-card" key={task.id}><label className="task-title-edit"><span className="task-checkbox" /><input aria-label={`Edit task ${task.title}`} key={task.title} defaultValue={task.title} disabled={busy} onBlur={(e) => fieldEdit(task.title, 'title', e.target.value.trim(), task.title)} /></label><div className="task-edit-fields"><label><span className="tiny-label">OWNER</span><div className="task-owner-select"><Avatar name={task.owner || '?'} small /><select aria-label={`Owner for ${task.title}`} value={task.owner} disabled={busy} onChange={(e) => fieldEdit(task.title, 'owner', e.target.value, task.owner)}><option value="">Choose owner</option>{['Priya', 'Rahul', 'Ananya'].map((p) => <option key={p}>{p}</option>)}</select></div></label><label><span className="tiny-label">DUE DATE</span><input aria-label={`Due date for ${task.title}`} type="date" value={task.due_date ?? ''} disabled={busy} onChange={(e) => fieldEdit(task.title, 'due_date', e.target.value, task.due_date)} /></label></div>{task.raw_due_phrase && <p className="raw-phrase">You said “{task.raw_due_phrase}”</p>}{value.questions.filter((q) => q.item_id === task.id).map((q) => <p className="question-hint" key={q.id}><MessageSquare size={12} />{q.prompt}</p>)}</Card>)}
      </section>
    </div>
    {!!value.ripples?.length && <section className="ripple-section"><div className="section-heading"><h2><GitFork size={18} />The ripple effect.</h2><span className="tag">Existing work, considered</span></div><p className="section-intro">A new decision can change a promise already made. Choose which updates to apply.</p><Card className="ripple-list">{value.ripples.map((ripple) => {
      const kept = ripple.conflict_id && resolutions[ripple.conflict_id] === 'keep_old'
      const applying = !kept && (rippleActions[ripple.id] ?? ripple.default_action) === 'apply'
      return <label className={`ripple-row ${kept ? 'ripple-disabled' : ''}`} key={ripple.id}><input type="checkbox" checked={Boolean(applying)} disabled={Boolean(kept) || busy} onChange={(e) => setRippleActions((all) => ({ ...all, [ripple.id]: e.target.checked ? 'apply' : 'skip' }))} /><span className="ripple-kind">{ripple.kind === 'reschedule' ? 'Move date' : ripple.kind === 'cancel' ? 'Cancel' : 'Update scope'}</span><div><strong>{ripple.task?.title ?? 'New work without an owner'}</strong><p>{kept ? 'Previous decision kept. This update will be skipped.' : ripple.reason}</p>{!kept && (ripple.proposal.title || ripple.proposal.due_date) && <span className="ripple-proposal"><ArrowDown size={11} />{ripple.proposal.title ?? `New due date: ${formatDate(ripple.proposal.due_date!)}`}</span>}</div>{ripple.task?.owner && <Avatar name={ripple.task.owner} small />}</label>
    })}</Card></section>}
    <section className="voice-edit-section"><div className="section-heading"><h2><AudioLines size={18} />A word from you changes things.</h2><span className="tiny-label">VOICE EDITS WELCOME</span></div><form onSubmit={(e) => { e.preventDefault(); if (instruction.trim()) edit.mutate(instruction.trim()) }}><div className="voice-edit-input"><Textarea aria-label="Tell Quorum what to change" placeholder="Tell Quorum what to change…" value={instruction} onChange={(e) => setInstruction(e.target.value)} rows={2} /><Button size="icon" type="submit" aria-label="Apply spoken edits" disabled={!instruction.trim() || busy}>{edit.isPending ? <LoaderCircle size={16} className="spin" /> : <ArrowRight size={17} />}</Button></div><div className="voice-examples"><span>Try saying</span><button type="button" onClick={() => setInstruction('Assign the investor update to Priya, due 2026-11-05')}>“Assign the investor update to Priya, due 2026-11-05”</button><button type="button" onClick={() => setInstruction('Drop the investor update')}>“Drop the investor update”</button></div></form>{edit.error && <p role="alert" className="inline-error">{errorMessage(edit.error)}</p>}<AnimatePresence>{!!changes.length && <motion.div className="changes-diff" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}><span className="tiny-label">HERE’S WHAT CHANGED</span>{changes.map((change, i) => <p key={i}><Check size={13} />{change}</p>)}</motion.div>}</AnimatePresence></section>
    {!!value.heads_up?.length && <details className="heads-up-details"><summary><Send size={14} />A personal heads-up, ready for each teammate<span>{value.heads_up.length} drafts</span><ChevronRight size={15} /></summary><div className="heads-up-grid">{value.heads_up.map((h) => <Card key={h.person}><div className="with-avatar"><Avatar name={h.person} small /><strong>{h.person}</strong></div><ReactMarkdown>{h.message_md}</ReactMarkdown></Card>)}</div><p className="muted">Draft previews. Actual notes follow the resolutions and ripple actions you approve.</p></details>}
    <div className="approval-bar"><div><ShieldCheck size={19} /><div><strong>{unanswered ? `${unanswered} question${unanswered > 1 ? 's' : ''} still need an answer` : unresolved ? `${unresolved} conflict${unresolved > 1 ? 's' : ''} still need your call` : 'All clear. You’re in control.'}</strong><span>{unanswered ? 'Choose an owner and deadline, or remove the task with a voice edit.' : 'Nothing changes until you approve.'}</span></div></div><div className="button-row"><Button variant="ghost" disabled={busy} onClick={() => setRejectionOpen(!rejectionOpen)}>Reject</Button><Button disabled={busy || unanswered > 0 || unresolved > 0} onClick={() => approve.mutate()}>{approve.isPending ? 'Putting things in motion…' : 'Approve & send'}<ArrowUpRight size={15} /></Button></div></div>
    {rejectionOpen && <Card className="reject-confirm"><span>Set this debrief aside? No tasks or decisions will change.</span><Button variant="outline" size="sm" onClick={() => setRejectionOpen(false)}>Keep reviewing</Button><Button size="sm" disabled={busy} onClick={() => reject.mutate()}><X size={13} />Reject debrief</Button></Card>}
    {(approve.error || reject.error) && <p role="alert" className="inline-error">{errorMessage(approve.error ?? reject.error)}</p>}
    {executionFailed && <Card className="reject-confirm"><span>Your approval was recorded, but execution stopped. Retry resumes the failed agent without approving twice.</span><Button disabled={retryExecution.isPending} onClick={() => retryExecution.mutate()}>Retry execution<ArrowRight size={14} /></Button></Card>}
    {retryExecution.error && <p role="alert" className="inline-error">{errorMessage(retryExecution.error)}</p>}
  </>
}
function ChevronDownIcon() { return <ChevronRight size={11} /> }
