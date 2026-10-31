import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { CalendarDays, CheckCheck, Clock3, FileText, Sparkles } from 'lucide-react'
import { api } from '@/api'
import { Avatar, ErrorState, Loading, PageHeading, SourceLink, TaskList } from '@/components/shared'
import { Card } from '@/components/ui/card'
import { formatDate } from '@/lib/utils'

export default function Digest() {
  const [person, setPerson] = useState('Priya')
  const [week, setWeek] = useState('')
  const people = useQuery({ queryKey: ['quorum', 'people'], queryFn: () => api.getPeople() })
  const digest = useQuery({ queryKey: ['quorum', 'digest', person, week], queryFn: () => api.getDigest(person, week || undefined) })
  return <>
    <PageHeading number="06" eyebrow="THE WEEK, WITHOUT THE CATCH-UP CALL" title="Big picture." soft="Personal to you." description="A thoughtful round-up of what moved, what’s due, and what needs a nudge. Built from the meetings you were already in." />
    <div className="digest-toolbar"><div className="person-picker" aria-label="Choose a teammate">{(people.data ?? ['Priya', 'Rahul', 'Ananya'].map((name) => ({ name }))).map((p) => <button key={p.name} aria-pressed={p.name === person} className={p.name === person ? 'selected' : ''} onClick={() => setPerson(p.name)}><Avatar name={p.name} small />{p.name}</button>)}</div><label className="inline-date-label"><CalendarDays size={14} /><span>Week of</span><input type="date" aria-label="Digest week starting" value={week || digest.data?.week_of || ''} onChange={(e) => {
      if (!e.target.value) { setWeek(''); return }
      const date = new Date(`${e.target.value}T12:00:00Z`); date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7); setWeek(date.toISOString().slice(0, 10))
    }} /></label></div>
    {digest.isPending ? <Loading label="A little perspective on the week…" /> : digest.error ? <ErrorState error={digest.error} retry={() => void digest.refetch()} /> : digest.data && <>
      <div className="digest-stats">{[{ icon: CheckCheck, number: digest.data.done.length, label: 'DONE & DUSTED' }, { icon: CalendarDays, number: digest.data.due.length, label: 'DUE THIS WEEK' }, { icon: Clock3, number: digest.data.overdue.length, label: 'NEED A NUDGE' }].map(({ icon: Icon, number, label }) => <Card key={label}><div><Icon size={17} /><span className="tiny-label">{label}</span></div><strong>{String(number).padStart(2, '0')}</strong></Card>)}</div>
      <div className="digest-columns"><Card className="markdown-card digest-letter"><div className="digest-letter-head"><span className="mini-brand-mark">q</span><span>YOUR WEEKLY NOTE</span><span>{formatDate(digest.data.week_of, { year: 'numeric' })}</span></div><ReactMarkdown>{digest.data.summary_md}</ReactMarkdown>{!!digest.data.decisions.length && <div className="digest-decisions"><h3><FileText size={16} />Decisions you shaped</h3>{digest.data.decisions.map((d) => <div key={d.id}><p>{d.statement}</p><SourceLink meetingId={d.meeting_id} title="The conversation" date={d.date} /></div>)}</div>}<div className="digest-signoff"><Sparkles size={15} /><span>Less remembering. More moving forward.<br /><strong>— Quorum</strong></span></div></Card><div className="digest-task-sections"><Card><h3>Coming due<span>{digest.data.due.length}</span></h3><TaskList tasks={digest.data.due} empty="No deadlines this week. Keep the momentum." /></Card><Card><h3>Worth a nudge<span>{digest.data.overdue.length}</span></h3><TaskList tasks={digest.data.overdue} empty="All caught up. That’s a good feeling." /></Card><Card><h3>Done & dusted<span>{digest.data.done.length}</span></h3><TaskList tasks={digest.data.done} empty="Your next completed commitment will appear here." /></Card></div></div>
    </>}
  </>
}
