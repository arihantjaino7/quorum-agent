import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Background, Controls, MarkerType, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import ReactMarkdown from 'react-markdown'
import { ArrowRight, CalendarDays, Clock3, GitFork, History, Radar, Sparkles } from 'lucide-react'
import { api } from '@/api'
import { Avatar, Empty, ErrorState, Loading, PageHeading, TaskList } from '@/components/shared'
import { Card } from '@/components/ui/card'
import { useApp } from '@/lib/app-context'
import { formatDate } from '@/lib/utils'

const views = [
  { id: 'timeline', label: 'Timeline', icon: History }, { id: 'lineage', label: 'Decision map', icon: GitFork },
  { id: 'time-machine', label: 'Time machine', icon: Clock3 }, { id: 'brief', label: 'Walk-in brief', icon: Sparkles },
  { id: 'radar', label: 'Change radar', icon: Radar },
] as const
type View = typeof views[number]['id']

export default function Memory() {
  const { project, theme } = useApp()
  const [searchParams] = useSearchParams()
  const selectedMeeting = searchParams.get('meeting')
  const [view, setView] = useState<View>('timeline')
  const [asOf, setAsOf] = useState('2026-10-24')
  const decisions = useQuery({ queryKey: ['quorum', 'decisions', project, 'all'], queryFn: () => api.getDecisions({ project, include_superseded: true }) })
  const meetings = useQuery({ queryKey: ['quorum', 'meetings', project], queryFn: () => api.getMeetings(project) })
  const graph = useQuery({ queryKey: ['quorum', 'graph', project], queryFn: () => api.getDecisionGraph(project), enabled: view === 'lineage' })
  const snapshot = useQuery({ queryKey: ['quorum', 'snapshot', project, asOf], queryFn: () => api.getDecisionsAsOf(project, asOf), enabled: view === 'time-machine' && Boolean(asOf) })
  const brief = useQuery({ queryKey: ['quorum', 'brief', project], queryFn: () => api.getBrief(project), enabled: view === 'brief' })
  const radar = useQuery({ queryKey: ['quorum', 'radar', project], queryFn: () => api.getRadar(project), enabled: view === 'radar' })
  const activeQuery = view === 'lineage' ? graph : view === 'time-machine' ? snapshot : view === 'brief' ? brief : view === 'radar' ? radar : decisions
  const topics = [...new Set(decisions.data?.map((d) => d.topic_key))]
  return <>
    <PageHeading number="03" eyebrow="CONTEXT DOESN’T HAVE TO GET LOST" title="Every decision." soft="The whole backstory." description="What we decided, why we changed our minds, and what it means for the work ahead. One shared memory for your team." />
    <div className="page-tabs" role="tablist" aria-label="Memory views">{views.map(({ id, label, icon: Icon }) => <button id={`memory-tab-${id}`} key={id} role="tab" aria-selected={view === id} aria-controls="memory-panel" className={view === id ? 'selected' : ''} onClick={() => setView(id)}><Icon size={14} />{label}</button>)}</div>
    <section role="tabpanel" id="memory-panel" aria-labelledby={`memory-tab-${view}`}>
      {activeQuery.isPending ? <Loading /> : activeQuery.error ? <ErrorState error={activeQuery.error} retry={() => void activeQuery.refetch()} /> : <>
        {view === 'timeline' && <>
          <div className="section-heading memory-summary"><span className="muted">{decisions.data?.length ?? 0} decisions · {meetings.data?.length ?? 0} meetings</span><span className="tag"><span className="status-dot" />A living record</span></div>
          {!decisions.data?.length && <Empty title="The first decision is a beginning.">Approve a meeting review to start building a shared memory.</Empty>}
          {meetings.data?.filter((meeting) => decisions.data?.some((d) => d.meeting_id === meeting.id) || meeting.id === selectedMeeting).map((meeting) => <section key={meeting.id} className={`timeline-meeting ${selectedMeeting === meeting.id ? 'source-highlight' : ''}`} id={meeting.id}>
            <div className="timeline-date"><span>{formatDate(meeting.date, { month: 'short' })}</span><span className="timeline-node" /></div>
            <div className="timeline-body"><div className="section-heading"><div><div className="tiny-label">{meeting.source_type === 'voice' ? 'VOICE DEBRIEF' : 'MEETING TRANSCRIPT'}{selectedMeeting === meeting.id && ' · SOURCE MEETING'}</div><h2>{meeting.title}</h2></div><span className="with-avatar"><Avatar name={meeting.speaker} small />{meeting.speaker}</span></div>
              {decisions.data?.filter((d) => d.meeting_id === meeting.id).map((d) => <Card className={`timeline-decision ${d.status}`} key={d.id}><div className="timeline-decision-main"><span className="decision-small-icon"><GitFork size={15} /></span><div><span className="tiny-label">{d.topic_key.replaceAll('_', ' ')}</span><h3>{d.statement}</h3>{d.rationale && <p>{d.rationale}</p>}</div><span className="tag">{d.status === 'superseded' ? 'Replaced' : 'Current'}</span></div>{d.source_quote && <details className="source-quote"><summary>In their words<ArrowRight size={12} /></summary><blockquote>“{d.source_quote}”</blockquote></details>}{d.superseded_by && <div className="superseded-by"><GitFork size={12} />Replaced by: {decisions.data?.find((next) => next.id === d.superseded_by)?.statement ?? 'A later decision'}</div>}</Card>)}
              {!decisions.data?.some((d) => d.meeting_id === meeting.id) && <p className="quiet-empty">This meeting is awaiting review. Its decisions enter memory after approval.</p>}
            </div>
          </section>)}
        </>}
        {view === 'lineage' && <><div className="section-heading"><h2>Follow the change of mind.</h2><span className="muted">Arrows point from a new decision to the one it replaces.</span></div><Card className="decision-graph">{graph.data?.nodes.length ? <ReactFlow colorMode={theme} nodes={graph.data.nodes.map((node) => {
          const decision = decisions.data?.find((d) => d.id === node.id)
          const row = Math.max(0, topics.indexOf(decision?.topic_key ?? ''))
          return { id: node.id, position: { x: node.status === 'superseded' ? 0 : 400, y: row * 180 }, data: { label: <div className="graph-node-content"><span>{node.status === 'superseded' ? 'PREVIOUS' : 'CURRENT'} · {formatDate(node.date)}</span><strong>{node.label}</strong><small>{node.meeting_title}</small></div> }, className: `graph-node ${node.status}`, style: { width: 285 }, sourcePosition: Position.Left, targetPosition: Position.Right }
        })} edges={graph.data.edges.map((edge) => ({ id: `${edge.source}-${edge.target}`, ...edge, label: 'replaces', markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: 'var(--accent)' } }))} fitView nodesDraggable={false} nodesConnectable={false} minZoom={0.4} maxZoom={1.5}><Background color="var(--line)" gap={24} /><Controls showInteractive={false} /></ReactFlow> : <Empty title="No decision map yet.">Your first approved decisions will appear here.</Empty>}</Card></>}
        {view === 'time-machine' && <><div className="section-heading"><h2>What did we believe back then?</h2><label className="inline-date-label"><CalendarDays size={15} /><input aria-label="Decision snapshot date" type="date" value={asOf} onChange={(e) => { if (e.target.value) setAsOf(e.target.value) }} /></label></div><p className="section-intro">A snapshot of the team’s decisions as of {formatDate(asOf, { year: 'numeric' })}.</p><div className="snapshot-grid">{snapshot.data?.decisions.map((d) => <Card key={d.id}><span className="tiny-label">{d.topic_key.replaceAll('_', ' ')}</span><h3>{d.statement}</h3><p>{d.rationale}</p><span className="source-link">{d.made_by} · {formatDate(d.date)}</span></Card>)}</div>{!snapshot.data?.decisions.length && <Empty title="Before the first conversation.">There are no recorded decisions on this date. Choose a later day.</Empty>}{!!snapshot.data?.changed_since.length && <Card className="changed-since"><h3>What changed since then</h3>{snapshot.data.changed_since.map((change) => <div key={change.topic_key}><span className="tiny-label">{change.topic_key.replaceAll('_', ' ')}</span><p><s>{change.then.statement}</s><ArrowRight size={14} />{change.now.statement}</p></div>)}</Card>}</>}
        {view === 'brief' && brief.data && <><Card className="brief-hero"><span className="tag"><Sparkles size={12} />Your 60-second catch-up</span><h2>{brief.data.headline}</h2><span className="muted">As of {formatDate(brief.data.as_of, { year: 'numeric' })}</span></Card><div className="brief-columns"><Card className="markdown-card"><ReactMarkdown>{brief.data.script_md}</ReactMarkdown><h3>Worth a conversation</h3><ol className="agenda-list">{brief.data.agenda.map((item) => <li key={item}>{item}</li>)}</ol></Card><div><Card className="brief-tasks"><h3>Coming up soon<span>{brief.data.due_soon.length}</span></h3><TaskList tasks={brief.data.due_soon} /></Card><Card className="brief-tasks"><h3>Needs a follow-up<span>{brief.data.overdue.length}</span></h3><TaskList tasks={brief.data.overdue} /></Card></div></div></>}
        {view === 'radar' && <><div className="section-heading"><h2>Spot the decisions that won’t sit still.</h2></div><p className="section-intro">A little awareness before another reversal creates more rework.</p><div className="radar-list">{radar.data?.topics.map((topic) => <Card key={topic.topic_key}><div className="radar-topic-head"><span className="decision-small-icon"><Radar size={18} /></span><div><h3>{topic.label}</h3><span>{topic.versions} version{topic.versions !== 1 ? 's' : ''} · last changed {formatDate(topic.last_changed)}</span></div><span className="tag">{topic.flips ? `${topic.flips} reversal${topic.flips > 1 ? 's' : ''}` : 'Steady direction'}</span></div><div className="churn-meter" aria-label={`Change rate ${Math.round(topic.churn * 100)} percent`}><span style={{ transform: `scaleX(${topic.churn})` }} /></div><p>{topic.note}</p><details className="source-quote"><summary>See the history<ArrowRight size={12} /></summary>{topic.statements.map((s) => <p key={s.decision_id}>{formatDate(s.date)} · {s.statement}</p>)}</details></Card>)}</div></>}
      </>}
    </section>
  </>
}

