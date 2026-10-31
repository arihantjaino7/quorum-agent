import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowUpRight, Bell, ChevronDown, Clock3, Moon, Plus, RotateCcw, Sun, X } from 'lucide-react'
import Lenis from 'lenis'
import 'lenis/dist/lenis.css'
import '@/home/home.css'
import './inner-scale.css'
import './inner.css'
import { api, useMocks } from '@/api'
import { useApp } from '@/lib/app-context'
import { errorMessage, formatDate } from '@/lib/utils'

const NAV = [
  { to: '/memory', label: 'Memory' }, { to: '/ask', label: 'Ask' }, { to: '/board', label: 'Board' }, { to: '/digest', label: 'Digest' },
]

/** Shared shell for every page after the first: the home page's floating bar, ambient light and smooth scrolling. */
export function Layout() {
  const { project, setProject, theme, toggleTheme, notify } = useApp()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [clockOpen, setClockOpen] = useState(false)
  const [clockInput, setClockInput] = useState('2026-11-03T09:00')
  const clock = useQuery({ queryKey: ['quorum', 'clock'], queryFn: () => api.getClock() })
  const projects = useQuery({ queryKey: ['quorum', 'projects'], queryFn: () => api.getProjects() })
  const clockMutation = useMutation({ mutationFn: (now: string) => api.setClock(now), onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['quorum'] }); setClockOpen(false); notify('Demo clock updated. Your deadlines follow along.')
  } })
  const reminders = useMutation({ mutationFn: () => api.runReminders(), onSuccess: (result) => {
    void queryClient.invalidateQueries({ queryKey: ['quorum'] })
    notify(result.sent.length ? `${result.sent.length} reminder${result.sent.length > 1 ? 's' : ''} ${useMocks ? 'recorded in the demo log' : 'processed'}.` : 'No new reminders due within the next 24 hours.')
  }, onError: (error) => notify(errorMessage(error)) })
  const reset = useMutation({ mutationFn: () => api.resetDemo(), onSuccess: () => {
    try { localStorage.removeItem('quorum-last-run'); localStorage.removeItem('quorum-unlocked') } catch { /* Reset is still complete in memory. */ }
    queryClient.clear(); navigate('/'); notify('Fresh start. The original Pocket meeting is back in memory.')
  }, onError: (error) => notify(errorMessage(error)) })

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const instance = new Lenis({ autoRaf: true, lerp: 0.09 })
    return () => instance.destroy()
  }, [])

  return <div className="home inner" onMouseMove={(e) => {
    e.currentTarget.style.setProperty('--px', `${e.clientX}px`); e.currentTarget.style.setProperty('--py', `${e.clientY}px`)
  }}>
    <div className="ambient" aria-hidden><span className="blob b1" /><span className="blob b2" /><span className="blob b3" /><span className="grid" /><span className="cursor-glow" /></div>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="home-bar">
      <Link to="/" className="brand" aria-label="Quorum home"><span className="brand-mark">q<span /></span><span>quorum<span className="brand-period">.</span></span></Link>
      <nav className="home-nav" aria-label="Workspace">
        {NAV.map((n) => {
          const active = location.pathname.startsWith(n.to)
          return <NavLink key={n.to} to={n.to} onClick={() => setClockOpen(false)} className={active ? 'is-active' : ''} aria-current={active ? 'page' : undefined}>
            {active && <motion.span className="nav-pill" layoutId="nav-pill" transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
            <span>{n.label}</span>
          </NavLink>
        })}
      </nav>
      <div className="home-bar-actions">
        {(projects.data?.length ?? 0) > 1 && <label className="inner-select"><select aria-label="Select project" value={project} onChange={(e) => setProject(e.target.value)}>
          {projects.data!.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}</select><ChevronDown size={12} /></label>}
        <div className="popover-anchor">
          <button type="button" className="clock-pill" onClick={() => setClockOpen(!clockOpen)} aria-expanded={clockOpen} aria-controls="clock-popover">
            <Clock3 size={14} /><span>{clock.data ? formatDate(clock.data.now, { year: 'numeric' }) : '…'}</span></button>
          <AnimatePresence>{clockOpen && <motion.section className="popover clock-popover" id="clock-popover" aria-label="Demo clock"
            initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }}>
            <div className="section-heading"><h3>A little time travel.</h3><button type="button" aria-label="Close demo clock" onClick={() => setClockOpen(false)}><X size={15} /></button></div>
            <p>Move the demo clock to see upcoming deadlines and reminders.</p>
            <form onSubmit={(e) => { e.preventDefault(); clockMutation.mutate(`${clockInput}:00`) }}>
              <label className="field-label" htmlFor="demo-clock">Jump to</label>
              <input id="demo-clock" type="datetime-local" value={clockInput} onChange={(e) => setClockInput(e.target.value)} required />
              <button type="submit" className="run-btn small" disabled={clockMutation.isPending}>Update clock<ArrowUpRight size={13} /></button>
            </form>
            {clockMutation.error && <p className="inline-error" role="alert">{errorMessage(clockMutation.error)}</p>}
          </motion.section>}</AnimatePresence>
        </div>
        <button type="button" className="icon-pill" title="Run reminders" aria-label="Run reminders" disabled={reminders.isPending} onClick={() => reminders.mutate()}><Bell size={15} /></button>
        <button type="button" className="icon-pill" title="Reset the demo" aria-label="Reset the demo" disabled={reset.isPending} onClick={() => reset.mutate()}><RotateCcw size={15} /></button>
        <button type="button" className="icon-pill" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={toggleTheme}>{theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}</button>
        <Link to="/" className="run-btn small new-debrief"><Plus size={14} />New debrief</Link>
      </div>
    </header>
    <main id="main-content" tabIndex={-1} className="inner-main">
      <motion.div key={location.pathname} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}><Outlet /></motion.div>
    </main>
    <ScrollRestoration />
    <footer className="inner-foot"><span><span className="tiny-q">q</span> A little less lost between meetings.</span><span>Quorum · Built with voice.</span></footer>
  </div>
}
