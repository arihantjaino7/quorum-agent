import { useState } from 'react'
import { NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, AudioLines, Bell, ChevronDown, Clock3, Moon, MoreHorizontal, Sun, X } from 'lucide-react'
import { api, useMocks } from '@/api'
import { Button } from '@/components/ui/button'
import { Avatar } from '@/components/shared'
import { useApp } from '@/lib/app-context'
import { errorMessage, formatDate } from '@/lib/utils'

const navigation = [
  { path: '/capture', name: 'Capture', detail: 'Start with your own words', number: '01' },
  { path: '/review', name: 'Review & resolve', detail: 'Your judgment, in the loop', number: '02' },
  { path: '/memory', name: 'Decision memory', detail: 'The story behind every call', number: '03' },
  { path: '/ask', name: 'Ask Quorum', detail: 'Answers that show their work', number: '04' },
  { path: '/board', name: 'Team board', detail: 'From a promise to progress', number: '05' },
  { path: '/digest', name: 'Weekly digest', detail: 'Everyone on the same page', number: '06' },
]

export function Layout() {
  const { project, setProject, theme, toggleTheme, notify } = useApp()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [clockOpen, setClockOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
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
    try { localStorage.removeItem('quorum-last-run') } catch { /* Reset is still complete in memory. */ }
    queryClient.clear(); setMenuOpen(false); navigate('/capture'); notify('Fresh start. The original Pocket meeting is back in memory.')
  }, onError: (error) => notify(errorMessage(error)) })
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar" aria-label="Workspace navigation">
      <NavLink to="/" className="brand" aria-label="Quorum home"><span className="brand-mark">q<span /></span><span>quorum<span className="brand-period">.</span></span></NavLink>
      <div className="workspace-caption">MEETINGS THAT REMEMBER</div>
      <div className="sidebar-label">YOUR WORKSPACE <span>↗</span></div>
      <nav className="nav-list">{navigation.map((item) => {
        const active = location.pathname.startsWith(item.path) || (item.path === '/review' && location.pathname.startsWith('/runs'))
        return <NavLink className={`nav-item ${active ? 'active' : ''}`} key={item.path} to={item.path} aria-current={active ? 'page' : undefined}>
          <span className="nav-number">{item.number}</span><span className="nav-copy"><strong>{item.name}</strong><small>{item.detail}</small></span>
          {active && <span className="nav-active-dot" />}
        </NavLink>
      })}</nav>
      <div className="sidebar-bottom">
        <div className="workspace-note"><AudioLines size={17} /><p>Good ideas deserve<br /><strong>a better memory.</strong></p></div>
        <div className="project-card"><span className="project-symbol">P</span><div><strong>{project}</strong><span>Product team workspace</span></div><ChevronDown size={14} /></div>
        <div className="sidebar-foot"><div className="avatar-stack"><Avatar name="Priya" small /><Avatar name="Rahul" small /><Avatar name="Ananya" small /></div><span>Made for the follow-through.</span></div>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumbs"><span>Workspace</span><span className="breadcrumb-slash">/</span><label className="project-select"><select aria-label="Select project" value={project} onChange={(e) => setProject(e.target.value)}>
          {(projects.data ?? [{ name: project }]).map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
        </select><ChevronDown size={12} /></label></div>
        <div className="topbar-actions">
          <span className="mode-badge"><i />{useMocks ? 'Demo workspace' : 'Connected workspace'}</span>
          <div className="popover-anchor"><button className="clock-button" onClick={() => { setClockOpen(!clockOpen); setMenuOpen(false) }} aria-expanded={clockOpen} aria-controls="clock-popover"><Clock3 size={13} /><span>Now: {clock.data ? formatDate(clock.data.now, { year: 'numeric' }) : '…'}</span><ChevronDown size={11} /></button>
            {clockOpen && <section className="popover clock-popover" id="clock-popover" aria-label="Demo clock"><div className="section-heading"><h3>A little time travel.</h3><button aria-label="Close demo clock" onClick={() => setClockOpen(false)}><X size={15} /></button></div><p>Move the demo clock to see upcoming deadlines and reminders.</p><form onSubmit={(e) => { e.preventDefault(); clockMutation.mutate(`${clockInput}:00`) }}><label className="field-label" htmlFor="demo-clock">Jump to</label><input id="demo-clock" type="datetime-local" value={clockInput} onChange={(e) => setClockInput(e.target.value)} required /><Button type="submit" size="sm" disabled={clockMutation.isPending}>Update clock<ArrowUpRight size={13} /></Button></form>{clockMutation.error && <p className="inline-error" role="alert">{errorMessage(clockMutation.error)}</p>}</section>}
          </div>
          <button className="icon-button reminder-button" title="Run reminders" aria-label="Run reminders" disabled={reminders.isPending} onClick={() => reminders.mutate()}><Bell size={16} /></button>
          <button className="icon-button" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={toggleTheme}>{theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}</button>
          <div className="popover-anchor"><button className="icon-button" aria-label="More workspace actions" aria-expanded={menuOpen} onClick={() => { setMenuOpen(!menuOpen); setClockOpen(false) }}><MoreHorizontal size={18} /></button>
            {menuOpen && <div className="popover workspace-menu"><strong>Demo controls</strong><p>Check reminders or start over with the sample meeting. This affects the {useMocks ? 'local demo' : 'connected backend'}.</p><div className="button-row"><Button variant="outline" size="sm" disabled={reminders.isPending} onClick={() => reminders.mutate()}><Bell size={12} />Run reminders</Button><Button variant="outline" size="sm" disabled={reset.isPending} onClick={() => reset.mutate()}>Reset demo workspace</Button></div></div>}
          </div>
        </div>
      </header>
      <main id="main-content" tabIndex={-1} className="stage"><Outlet /></main>
      <ScrollRestoration />
      <footer className="main-footer"><span><span className="tiny-q">q</span> A little less lost between meetings.</span><span>Quorum · Built with voice.</span></footer>
    </div>
  </div>
}
