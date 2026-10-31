import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { ArrowRight, ArrowUpRight, AudioLines, BookOpen, CornerDownLeft, LoaderCircle, Quote } from 'lucide-react'
import { api } from '@/api'
import { ErrorState, PageHeading, SourceLink } from '@/components/shared'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useApp } from '@/lib/app-context'
import { formatDate } from '@/lib/utils'
import type { AskResult } from '@/types'

const suggestions = [
  { title: 'Why did we pick Razorpay?', detail: 'Find the reason behind the decision.' },
  { title: 'Are we building for Android?', detail: 'Get the current answer, with context.' },
  { title: 'When are we launching?', detail: 'One date the whole team can agree on.' },
]
export default function Ask() {
  const { project } = useApp()
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<{ question: string; result: AskResult }[]>([])
  const ref = useRef<HTMLTextAreaElement>(null)
  const ask = useMutation({ mutationFn: (value: string) => api.ask(project, value), onSuccess: (result, submitted) => {
    setHistory((all) => [{ question: submitted, result }, ...all]); setQuestion('')
  } })
  return <>
    <PageHeading number="04" eyebrow="YOUR TEAM’S MEMORY, IN CONVERSATION" title="“Wait, why did we…”" soft="There’s a meeting for that." description="Ask in your own words. Get an answer grounded in what your team actually said, with the receipts to back it up." />
    <form className="ask-form" onSubmit={(e) => { e.preventDefault(); if (question.trim()) ask.mutate(question.trim()) }}><Card className="ask-input-card"><span className="ask-input-icon"><AudioLines size={21} /></span><Textarea ref={ref} aria-label="Ask your meeting memory" placeholder="Hold your Wispr key. What’s on your mind?" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && question.trim() && !ask.isPending) { e.preventDefault(); ask.mutate(question.trim()) } }} /><div className="ask-input-foot"><span><CornerDownLeft size={12} />Enter to ask · Shift + Enter for a new line</span><Button type="submit" disabled={!question.trim() || ask.isPending}>{ask.isPending ? <><LoaderCircle className="spin" size={15} />Looking back…</> : <>Ask your meetings<ArrowRight size={15} /></>}</Button></div></Card></form>
    {!history.length && <><div className="subsection-label ask-suggestions-label">A GOOD PLACE TO START</div><div className="ask-suggestions">{suggestions.map((item) => <button className="card" key={item.title} onClick={() => { setQuestion(item.title); ref.current?.focus() }}><span><BookOpen size={16} /><ArrowUpRight size={14} /></span><h3>{item.title}</h3><p>{item.detail}</p></button>)}</div><div className="ask-reassurance"><Quote size={28} strokeWidth={1} /><p>Good answers have a source.<br /><span>Every answer links back to the conversation.</span></p></div></>}
    {ask.error && <ErrorState error={ask.error} retry={() => ask.mutate(question.trim())} />}
    <div className="answer-history" aria-live="polite">{history.map(({ question: submitted, result }, index) => <motion.section key={`${submitted}-${history.length - index}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className="answered-question"><AudioLines size={16} /><h2>{submitted}</h2></div><Card className="answer-card"><div className="answer-byline"><span className="mini-brand-mark">q</span><strong>Quorum</strong><span>From your meeting memory</span></div><div className="answer-prose"><ReactMarkdown>{result.answer}</ReactMarkdown></div>{!!result.citations.length && <><div className="subsection-label">STRAIGHT FROM THE SOURCE <span>{result.citations.length}</span></div><div className="citation-grid">{result.citations.map((citation, i) => <div className="citation-card" key={`${citation.meeting_id}-${i}`}><div><span className="citation-number">{String(i + 1).padStart(2, '0')}</span><span>{formatDate(citation.date, { year: 'numeric' })}</span></div><blockquote>“{citation.quote}”</blockquote><SourceLink meetingId={citation.meeting_id} title={citation.meeting_title} /></div>)}</div></>}</Card></motion.section>)}</div>
  </>
}
