import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { ArrowUpRight, CircleAlert, LoaderCircle, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { errorMessage, formatDate, initials } from '@/lib/utils'
import type { Task } from '@/types'

export function PageHeading({ number, eyebrow, title, soft, description, children }: {
  number: string; eyebrow: string; title: string; soft: string; description?: string; children?: ReactNode
}) {
  return <div className="page-heading">
    <span className="ghost-number" aria-hidden="true">{number}</span>
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="eyebrow"><span>({number})</span>{eyebrow}</div>
      <h1>{title}<br /><span>{soft}</span></h1>
      {description && <p className="lede">{description}</p>}
      {children}
    </motion.div>
  </div>
}
export function Avatar({ name, small = false }: { name: string; small?: boolean }) {
  return <span className={`avatar ${small ? 'avatar-sm' : ''} avatar-${name.toLowerCase()}`} aria-label={name}>{initials(name)}</span>
}
export function Loading({ label = 'Bringing things together…' }: { label?: string }) {
  return <div className="state-panel" role="status"><LoaderCircle className="spin" size={23} /><h3>{label}</h3><p>Just a moment. Your meeting memory is on its way.</p></div>
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return <div className="state-panel" role="alert"><CircleAlert size={24} /><h3>Let’s try that again.</h3><p>{errorMessage(error)}</p>{retry && <Button variant="outline" onClick={retry}><RotateCcw size={14} />Try again</Button>}</div>
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="state-panel"><span className="empty-mark">Q</span><h3>{title}</h3><p>{children}</p></div>
}
export function SourceLink({ meetingId, title, date }: { meetingId: string; title?: string; date?: string }) {
  return <Link className="source-link" to={`/memory?meeting=${encodeURIComponent(meetingId)}`}>{title ?? 'Source meeting'}{date && <> · {formatDate(date)}</>}<ArrowUpRight size={12} /></Link>
}
export function TaskList({ tasks, empty = 'Nothing here. A little breathing room.' }: { tasks: Task[]; empty?: string }) {
  return <div className="simple-task-list">{tasks.length ? tasks.map((task) => <div className="simple-task" key={task.id}>
    <span className={`task-dot ${task.status === 'done' ? 'is-done' : ''}`} /><div><strong>{task.title}</strong><span>{task.owner || 'Unassigned'} · {task.due_date ? formatDate(task.due_date) : 'No deadline'}</span></div>
    {task.tracker_url && <a href={task.tracker_url} target="_blank" rel="noreferrer" aria-label={`Open tracker for ${task.title}`}><ArrowUpRight size={15} /></a>}
  </div>) : <p className="quiet-empty">{empty}</p>}</div>
}
