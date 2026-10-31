import { useEffect, useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { Check, X } from 'lucide-react'
import { AppContext } from '@/lib/app-context'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 20_000, retry: 1, refetchOnWindowFocus: false }, mutations: { retry: false } } })
export function Providers({ children }: { children: ReactNode }) {
  const [project, setProject] = useState('Pocket')
  const [theme, setTheme] = useState<'light' | 'dark'>(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
  const [toast, setToast] = useState('')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('quorum-theme', theme) } catch { /* Theme still works without storage. */ }
  }, [theme])
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(''), 6000)
    return () => clearTimeout(timer)
  }, [toast])
  return <QueryClientProvider client={queryClient}>
    <MotionConfig reducedMotion="user" transition={{ duration: 0.35, ease: [0.2, 0.7, 0.2, 1] }}>
      <AppContext.Provider value={{ project, setProject, theme, toggleTheme: () => setTheme((t) => t === 'light' ? 'dark' : 'light'), notify: setToast }}>
        {children}
        <div className="toast-region" role="status" aria-live="polite"><AnimatePresence>
          {toast && <motion.div className="toast" key={toast} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
            <Check size={16} /><span>{toast}</span><button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={14} /></button>
          </motion.div>}
        </AnimatePresence></div>
      </AppContext.Provider>
    </MotionConfig>
  </QueryClientProvider>
}
