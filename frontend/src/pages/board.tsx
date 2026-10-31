import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Bell, Check, CheckCheck, Circle, SlidersHorizontal } from 'lucide-react'
import { api, useMocks } from '@/api'
import { Avatar, Empty, ErrorState, Loading, PageHeading, SourceLink } from '@/components/shared'
import { Card } from '@/components/ui/card'
import { useApp } from '@/lib/app-context'
import { errorMessage, formatDate } from '@/lib/utils'

export default function Board() {
  const { project, notify } = useApp()
  const client = useQueryClient()
  const [filter, setFilter] = useState('all')
  const [showDone, setShowDone] = useState(true)
  const tasks = useQuery({ queryKey: ['quorum', 'tasks', project], queryFn: () => api.getTasks({ project }) })
  const clock = useQuery({ queryKey: ['quorum', 'clock'], queryFn: () => api.getClock() })
  const people = useQuery({ queryKey: ['quorum', 'people'], queryFn: () => api.getPeople() })
  const health = useQuery({ queryKey: ['quorum', 'health'], queryFn: () => api.getHealth() })
  const update = useMutation({ mutationFn: ({ id, status }: { id: string; status: 'todo' | 'done' }) => api.updateTask(id, status), onSuccess: () => void client.invalidateQueries({ queryKey: ['quorum'] }), onError: (error) => notify(errorMessage(error)) })
  const all = tasks.data ?? []
  const owners = [...new Set([...(people.data?.map((p) => p.name) ?? []), ...all.map((t) => t.owner)])].filter(Boolean)
  const displayedOwners = filter === 'all' ? owners : [filter]
  const open = all.filter((t) => t.status === 'todo')
  return <>
    <PageHeading number="05" eyebrow="THE FOLLOW-THROUGH LIVES HERE" title="Less “who’s doing that?”" soft="More getting it done." description="Every commitment, with a name, a date, and a conversation behind it. This is where your meetings move forward." />
    <div className="board-toolbar"><div className="board-stats"><span><Circle size={12} />{open.length} to do</span><span><CheckCheck size={14} />{all.length - open.length} done</span></div><div className="board-filters"><label><SlidersHorizontal size={13} /><select aria-label="Filter tasks by owner" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="all">Everyone</option>{owners.map((o) => <option key={o}>{o}</option>)}</select></label><label className="checkbox-label"><input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />Show completed</label></div></div>
    {health.data && <div className="integration-note"><span className="tag">{health.data.integrations.notion ? 'Notion connected' : 'Notion not connected'}</span><span>{useMocks ? 'Demo tasks stay in this browser. Tracker links appear when an integration creates them.' : 'Approved tasks appear here. Connected trackers provide a direct link.'}</span></div>}
    {tasks.isPending ? <Loading /> : tasks.error ? <ErrorState error={tasks.error} retry={() => void tasks.refetch()} /> : !all.length ? <Empty title="A clear board, a fresh start.">Approve a meeting review and your team’s commitments will land here.</Empty> : <div className="owner-board" style={{ gridTemplateColumns: `repeat(${Math.min(displayedOwners.length, 3)}, minmax(0, 1fr))` }}>{displayedOwners.map((owner) => {
      const ownerTasks = all.filter((t) => t.owner === owner && (showDone || t.status !== 'done'))
      return <section className="owner-column" key={owner}><div className="owner-column-head"><Avatar name={owner} /><div><h3>{owner}</h3><span>{ownerTasks.filter((t) => t.status === 'todo').length} open commitments</span></div><span className="subtle-count">{ownerTasks.length}</span></div><div className="owner-task-list">{ownerTasks.map((task) => {
        const overdue = task.status !== 'done' && task.due_date && clock.data && task.due_date < clock.data.now.slice(0, 10)
        return <Card className={`board-task ${task.status === 'done' ? 'task-done' : ''}`} key={task.id}><div className="board-task-title"><button className="completion-toggle" aria-label={`${task.status === 'done' ? 'Mark as to do' : 'Mark as done'}: ${task.title}`} aria-pressed={task.status === 'done'} disabled={update.isPending} onClick={() => update.mutate({ id: task.id, status: task.status === 'done' ? 'todo' : 'done' })}>{task.status === 'done' && <Check size={12} />}</button><h3>{task.title}</h3></div><div className="board-task-meta"><span className={`due-tag ${overdue ? 'overdue' : ''}`}>{task.status === 'done' ? <Check size={11} /> : <Circle size={9} />}{task.due_date ? formatDate(task.due_date) : 'No deadline'}{overdue && ' · Overdue'}</span><span className="reminder-state" title={task.reminder_sent ? 'A reminder was sent or logged' : 'Reminder not sent yet'}><Bell size={12} />{task.reminder_sent ? 'Reminded' : task.status === 'done' ? 'Not needed' : 'Not sent'}</span></div><SourceLink meetingId={task.meeting_id} title="From a meeting" /><details className="task-source"><summary>The original commitment</summary><blockquote>“{task.source_quote}”</blockquote></details>{task.tracker_url && <a className="tracker-link" href={task.tracker_url} target="_blank" rel="noreferrer">Open task tracker<ArrowUpRight size={12} /></a>}</Card>
      })}{!ownerTasks.length && <div className="empty-column"><CheckCheck size={22} /><p>A little room to breathe.</p></div>}</div></section>
    })}</div>}
  </>
}
