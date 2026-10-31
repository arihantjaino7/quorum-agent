import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, ArrowUpRight, AudioLines, Check, ChevronDown, FileText, History, Mic, Paperclip, Sparkles, X } from 'lucide-react'
import { api, useMocks } from '@/api'
import { PageHeading, Avatar, SourceLink } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useApp } from '@/lib/app-context'
import { errorMessage, formatDate } from '@/lib/utils'
import { DEMO_THREAD, demoDebrief } from '@/mocks/fixtures'
import type { SourceType } from '@/types'

export default function Capture() {
  const { project } = useApp()
  const navigate = useNavigate()
  const [source, setSource] = useState<'voice' | 'transcript'>('voice')
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [speaker, setSpeaker] = useState('Priya')
  const [date, setDate] = useState('2026-10-31')
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const meetings = useQuery({ queryKey: ['quorum', 'meetings', project], queryFn: () => api.getMeetings(project) })
  const decisions = useQuery({ queryKey: ['quorum', 'decisions', project], queryFn: () => api.getDecisions({ project }) })
  const persons = useQuery({ queryKey: ['quorum', 'people'], queryFn: () => api.getPeople() })
  const ingest = useMutation({ mutationFn: async () => {
    const metadata = { project, title: title.trim() || 'Untitled meeting debrief', date, speaker,
      source_type: (file?.type.startsWith('audio/') || /\.(mp3|m4a|wav|webm)$/i.test(file?.name ?? '') ? 'audio' : source) as SourceType }
    return file ? api.ingestFile({ ...metadata, file }) : api.ingest({ ...metadata, text })
  }, onSuccess: ({ thread_id }) => {
    try { localStorage.setItem('quorum-last-run', thread_id) } catch { /* URL-based recovery still works. */ }
    navigate(`/runs/${encodeURIComponent(thread_id)}`)
  } })
  function loadDemo() {
    setSource('voice'); setTitle('Investor sync debrief'); setDate('2026-10-31'); setSpeaker('Priya'); setFile(null); setText(demoDebrief); setFileError('')
    inputRef.current?.focus()
  }
  function attachFile(next?: File) {
    if (!next) return
    if (!/\.(vtt|srt|txt|mp3|m4a|wav|webm)$/i.test(next.name)) { setFileError('Choose a .txt, .vtt, .srt, .mp3, .m4a, .wav or .webm file.'); return }
    if (next.size > 25 * 1024 * 1024) { setFileError('Keep this prototype’s uploads under 25 MB.'); return }
    setFileError(''); setFile(next); setSource('transcript')
  }
  const history = decisions.data ?? []
  return <>
    <PageHeading number="01" eyebrow="A LITTLE LESS LOST IN TRANSLATION" title="A meeting ends." soft="The work begins." description="The decisions, the detours, the “actually, let’s change that.” Just say it. Quorum remembers what matters." />
    <div className="capture-layout">
      <div>
        <form onSubmit={(e) => { e.preventDefault(); ingest.mutate() }}>
          <Card className={`capture-card ${dragging ? 'is-dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); attachFile(e.dataTransfer.files[0]) }}>
            <div className="capture-card-top"><div className="segmented" aria-label="Capture format">
              <button type="button" aria-pressed={source === 'voice'} className={source === 'voice' ? 'selected' : ''} onClick={() => setSource('voice')}><AudioLines size={14} />Voice debrief</button>
              <button type="button" aria-pressed={source === 'transcript'} className={source === 'transcript' ? 'selected' : ''} onClick={() => setSource('transcript')}><FileText size={14} />Transcript</button>
            </div><span className="capture-private"><span className="status-dot" />Your words. Your call.</span></div>
            <div className="capture-text-area">
              {!text && !file && <div className="capture-prompt" aria-hidden="true"><span className="mic-orbit"><Mic size={22} strokeWidth={1.5} /></span><h2>{source === 'voice' ? 'Hold your Wispr key and talk.' : 'Bring the whole conversation.'}</h2><p>{source === 'voice' ? 'Messy thoughts welcome. We’ll connect the dots.' : 'Paste a transcript, or drop a file right here.'}</p><div className="waveform">{[7, 12, 21, 14, 29, 18, 35, 24, 14, 26, 17, 30, 20, 11, 18, 8, 13, 6].map((height, index) => <i key={index} style={{ height }} />)}</div></div>}
              <Textarea ref={inputRef} className="debrief-input" aria-label={source === 'voice' ? 'Meeting voice debrief' : 'Meeting transcript'} placeholder="" value={text} onChange={(e) => { setText(e.target.value); if (file) setFile(null) }} disabled={ingest.isPending} />
              {file && <div className="attached-file"><FileText size={22} /><div><strong>{file.name}</strong><span>{(file.size / 1024).toFixed(1)} KB · ready to process</span></div><button type="button" aria-label="Remove attached file" onClick={() => setFile(null)}><X size={16} /></button></div>}
            </div>
            <div className="capture-input-foot"><button type="button" className="text-button" onClick={() => fileRef.current?.click()}><Paperclip size={14} />Attach a file</button><span>{text ? `${text.trim().split(/\s+/).length} words` : '.txt, .vtt, .srt or audio'}</span><input ref={fileRef} className="sr-only" tabIndex={-1} type="file" accept=".txt,.vtt,.srt,.mp3,.m4a,.wav,.webm,audio/*" aria-label="Upload transcript or audio" onChange={(e) => attachFile(e.target.files?.[0])} /></div>
            <div className="meeting-fields"><label className="meeting-title-field"><span>MEETING TITLE</span><input aria-label="Meeting title" placeholder="Give this conversation a name" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={180} /></label><label><span>SPEAKER</span><div className="speaker-field"><Avatar name={speaker} small /><select aria-label="Meeting speaker" value={speaker} onChange={(e) => setSpeaker(e.target.value)}>{(persons.data ?? ['Priya', 'Rahul', 'Ananya'].map((name) => ({ name }))).map((p) => <option key={p.name}>{p.name}</option>)}</select><ChevronDown size={12} /></div></label><label><span>MEETING DATE</span><input type="date" aria-label="Meeting date" value={date} onChange={(e) => setDate(e.target.value)} required /></label></div>
          </Card>
          {(fileError || ingest.error) && <p className="inline-error" role="alert">{fileError || errorMessage(ingest.error)}</p>}
          <div className="capture-actions"><div><span className="human-check"><Check size={13} />You review before anything goes out.</span>{useMocks && <span className="mock-hint">Local demo · sample debrief only</span>}</div><Button type="submit" disabled={ingest.isPending || (!text.trim() && !file)}>{ingest.isPending ? 'Connecting the dots…' : 'Turn this into action'}<ArrowRight size={16} /></Button></div>
        </form>
        <div className="demo-nudge"><span className="demo-spark"><Sparkles size={17} /></span><div><strong>Meet your meeting’s better half.</strong><p>Try a debrief with three decisions that change everything.</p></div><button className="text-button" onClick={loadDemo}>Try the demo<ArrowUpRight size={14} /></button></div>
      </div>
      <motion.aside className="memory-preview" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 }}>
        <div className="mini-eyebrow"><History size={14} />ALREADY IN MEMORY</div><h2>Your next meeting<br /><span>has a backstory.</span></h2><p>New decisions don’t happen in a vacuum. We’ll check them against what your team already agreed.</p>
        <div className="memory-stats"><div><strong>{String(meetings.data?.length ?? 0).padStart(2, '0')}</strong><span>meetings</span></div><div><strong>{String(history.length).padStart(2, '0')}</strong><span>decisions remembered</span></div></div>
        <div className="remembered-list">{history.slice(0, 3).map((d, index) => <div key={d.id} className="remembered-decision"><span className="memory-dot" /><span className="tiny-label">{['PLATFORM', 'LAUNCH', 'PAYMENTS'][index]}</span><strong>{d.statement}</strong><SourceLink meetingId={d.meeting_id} date={d.date} title="Team decision" /></div>)}{!history.length && <p>{decisions.isError ? 'Memory will appear when the backend reconnects.' : 'Your first approved decisions will appear here.'}</p>}</div>
        <Link className="text-button memory-preview-link" to="/memory">Explore decision memory<ArrowRight size={14} /></Link>
      </motion.aside>
    </div>
    <section className="recent-section"><div className="section-heading"><h3>Where we left off<span className="subtle-count">{meetings.data?.length ?? 0}</span></h3><Link className="text-button" to="/memory">All meeting memory<ArrowUpRight size={13} /></Link></div>
      {meetings.data?.slice(0, 2).map((meeting) => <Link key={meeting.id} to={`/memory?meeting=${encodeURIComponent(meeting.id)}`} className="recent-meeting"><span className="meeting-icon"><AudioLines size={18} /></span><div className="recent-meeting-copy"><strong>{meeting.title}</strong><span>{meeting.speaker} · {formatDate(meeting.date, { year: 'numeric' })}</span></div><span className="tag">In memory</span><ArrowUpRight size={15} /></Link>)}
      {!meetings.data?.length && <p className="quiet-empty">Your meetings will find a home here.</p>}
      {useMocks && <div className="quick-review-link">Want to see the decision moment? <Link to={`/review/${DEMO_THREAD}`}>Open the sample review<ArrowUpRight size={12} /></Link></div>}
    </section>
  </>
}
