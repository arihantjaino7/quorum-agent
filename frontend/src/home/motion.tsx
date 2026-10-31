import { useEffect, useRef, useState, type ReactNode } from 'react'
import { animate, motion, useInView, useMotionValue, useTransform } from 'framer-motion'

import { EASE, EASE_IN_OUT } from './constants'

/** Headline whose words rise out of a slot and come into focus, one after another. */
export function RiseWords({ lines, delay = 0, className }: { lines: { text: string; muted?: boolean }[]; delay?: number; className?: string }) {
  let index = 0
  return <h1 className={className}>
    {lines.map((line, li) => <span key={li} className={`rise-row ${line.muted ? 'is-muted' : ''}`}>
      {line.text.split(' ').map((word, wi) => {
        const i = index++
        return <span className="rise-slot" key={wi}>
          <motion.span className="rise-word" initial={{ y: '105%', filter: 'blur(10px)', opacity: 0 }}
            animate={{ y: '0%', filter: 'blur(0px)', opacity: 1 }} transition={{ duration: 1, delay: delay + i * 0.07, ease: EASE }}>
            {word}
          </motion.span>
        </span>
      })}
    </span>)}
  </h1>
}

/** A single line that rises in when it scrolls into view (the slot is observed, not the clipped text). */
export function RiseOnView({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return <motion.span className={`rise-slot is-block ${className ?? ''}`} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.5 }}>
    <motion.span className="rise-word is-block" variants={{ hidden: { y: '105%' }, show: { y: '0%' } }} transition={{ duration: 0.9, delay, ease: EASE }}>
      {children}
    </motion.span>
  </motion.span>
}

/** Fades and lifts content as it enters the viewport. */
export function Appear({ children, delay = 0, className, y = 24 }: { children: ReactNode; delay?: number; className?: string; y?: number }) {
  return <motion.div className={className} initial={{ opacity: 0, y, filter: 'blur(6px)' }} whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
    viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.8, delay, ease: EASE }}>{children}</motion.div>
}

/** Text that types itself out (remount with a new key to retype). */
export function Typewriter({ text, speed = 16 }: { text: string; speed?: number }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    let n = 0
    const id = setInterval(() => { n += 2; setShown(n); if (n >= text.length) clearInterval(id) }, speed)
    return () => clearInterval(id)
  }, [text, speed])
  return <span aria-label={text}><span aria-hidden>{text.slice(0, shown)}</span>
    {shown < text.length && <span className="type-caret" aria-hidden />}</span>
}

/** A number that counts up once visible. */
export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const value = useMotionValue(0)
  const rounded = useTransform(value, (v) => Math.round(v).toString())
  useEffect(() => {
    if (!inView) return
    const controls = animate(value, to, { duration: 1.3, ease: EASE })
    return () => controls.stop()
  }, [inView, to, value])
  return <motion.span ref={ref}>{rounded}</motion.span>
}

/** Strike that draws across the old decision, line by line, once it has been read. */
export function Strike({ children, off }: { children: ReactNode; off: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  const seen = useInView(ref, { once: true, amount: 0.9 })
  return <motion.span ref={ref} className="strike" initial={{ backgroundSize: '0% 2px' }}
    animate={{ backgroundSize: seen && !off ? '100% 2px' : '0% 2px' }}
    transition={{ duration: 0.9, delay: off ? 0 : 0.4, ease: EASE_IN_OUT }}>{children}</motion.span>
}

/**
 * Voice bars that breathe while idle and jump whenever words arrive. Wispr types the dictation into the box,
 * so every burst of text makes the bars dance, as if the page were listening.
 */
export function Waveform({ level, bars = 48 }: { level: number; bars?: number }) {
  const refs = useRef<(HTMLSpanElement | null)[]>([])
  const energy = useRef(0)
  const last = useRef(level)
  useEffect(() => {
    const delta = Math.max(0, level - last.current)
    last.current = level
    energy.current = Math.min(1, energy.current + delta / 40)
  }, [level])
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let frame = 0
    let t = 0
    const tick = () => {
      t += 1
      energy.current *= 0.94
      refs.current.forEach((el, i) => {
        if (!el) return
        const idle = 0.16 + 0.1 * Math.sin(t / 18 + i * 0.55)
        const live = energy.current * (0.35 + 0.65 * Math.abs(Math.sin(t / 5 + i * 1.7)) * Math.random())
        el.style.transform = `scaleY(${Math.min(1, idle + live)})`
      })
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])
  return <span className="voice-wave" aria-hidden>
    {Array.from({ length: bars }, (_, i) => <span key={i} ref={(el) => { refs.current[i] = el }} />)}
  </span>
}

/** The approval seal: a check that draws itself, rings that ripple out, and a small burst. */
export function Seal({ tone = 'accent' }: { tone?: 'accent' | 'muted' }) {
  const dots = Array.from({ length: 14 }, (_, i) => (i / 14) * Math.PI * 2)
  return <div className={`seal seal-${tone}`} aria-hidden>
    {[0, 1, 2].map((i) => <motion.span key={i} className="seal-ring" initial={{ scale: 1, opacity: 0.55 }}
      animate={{ scale: 2.6, opacity: 0 }} transition={{ duration: 1.6, delay: 0.35 + i * 0.28, ease: EASE }} />)}
    {dots.map((a, i) => <motion.span key={i} className="seal-dot" initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
      animate={{ x: Math.cos(a) * (90 + (i % 3) * 22), y: Math.sin(a) * (90 + (i % 3) * 22), opacity: 0, scale: 0.4 }}
      transition={{ duration: 1.1, delay: 0.3, ease: EASE }} />)}
    <motion.span className="seal-core" initial={{ scale: 0, rotate: -40 }} animate={{ scale: 1, rotate: 0 }}
      transition={{ type: 'spring', stiffness: 420, damping: 18, delay: 0.1 }}>
      <svg viewBox="0 0 52 52" width="58" height="58">
        <motion.path d={tone === 'accent' ? 'M14 27 L23 36 L39 18' : 'M17 17 L35 35 M35 17 L17 35'} fill="none" stroke="currentColor" strokeWidth="4.5"
          strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 0.55, delay: 0.45, ease: EASE }} />
      </svg>
    </motion.span>
  </div>
}
