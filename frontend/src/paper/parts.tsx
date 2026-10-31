import { useEffect, useState, type ReactNode } from 'react'
import { animate, motion, useInView, useMotionValue, useTransform } from 'framer-motion'
import { useRef } from 'react'

const EASE = [0.76, 0, 0.24, 1] as const

/** Lines that rise out of an invisible slot, like type being set. */
export function RiseLines({ lines, delay = 0, className, as: Tag = 'h1' }: {
  lines: ReactNode[]; delay?: number; className?: string; as?: 'h1' | 'h2' | 'h3' | 'p'
}) {
  return <Tag className={className}>
    {lines.map((line, i) => <span className="rise-slot" key={i}>
      <motion.span className="rise-line" initial={{ y: '108%' }} animate={{ y: '0%' }}
        transition={{ duration: 1.1, delay: delay + i * 0.12, ease: EASE }}>{line}</motion.span>
    </span>)}
  </Tag>
}

/** Same effect, but triggered when it scrolls into view. The unclipped slot is what gets observed. */
export function RiseOnView({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return <motion.span className={`rise-slot ${className ?? ''}`} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.5 }}>
    <motion.span className="rise-line" variants={{ hidden: { y: '108%' }, show: { y: '0%' } }}
      transition={{ duration: 0.9, delay, ease: EASE }}>{children}</motion.span>
  </motion.span>
}

/** A hairline that draws itself across (or down) the page. */
export function Rule({ vertical = false, delay = 0, double = false, className = '' }: {
  vertical?: boolean; delay?: number; double?: boolean; className?: string
}) {
  return <motion.div aria-hidden className={`rule ${vertical ? 'rule-v' : 'rule-h'} ${double ? 'rule-double' : ''} ${className}`}
    initial={vertical ? { scaleY: 0 } : { scaleX: 0 }} whileInView={vertical ? { scaleY: 1 } : { scaleX: 1 }}
    viewport={{ once: true }} transition={{ duration: 1.2, delay, ease: EASE }} />
}

/** Fades and lifts content in as it enters the viewport. */
export function Appear({ children, delay = 0, className, y = 28 }: { children: ReactNode; delay?: number; className?: string; y?: number }) {
  return <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.8, delay, ease: [0.2, 0.7, 0.2, 1] }}>{children}</motion.div>
}

/** Text that types itself out, character by character (remount with a new key to retype). */
export function Typewriter({ text, speed = 14, className }: { text: string; speed?: number; className?: string }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    let n = 0
    const id = setInterval(() => { n += 1; setShown(n); if (n >= text.length) clearInterval(id) }, speed)
    return () => clearInterval(id)
  }, [text, speed])
  return <span className={className} aria-label={text}><span aria-hidden>{text.slice(0, shown)}</span>
    {shown < text.length && <span className="type-caret" aria-hidden>▍</span>}</span>
}

/** A number that counts up once it is visible. */
export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const value = useMotionValue(0)
  const rounded = useTransform(value, (v) => Math.round(v).toString())
  useEffect(() => {
    if (!inView) return
    const controls = animate(value, to, { duration: 1.4, ease: [0.2, 0.7, 0.2, 1] })
    return () => controls.stop()
  }, [inView, to, value])
  return <motion.span ref={ref}>{rounded}</motion.span>
}

/** The rubber stamp: slams down from above with a little ink bleed. */
export function Stamp({ label, sub, tone = 'red', delay = 0 }: { label: string; sub: string; tone?: 'red' | 'grey'; delay?: number }) {
  return <motion.div className={`stamp stamp-${tone}`} role="img" aria-label={`${label}. ${sub}`}
    initial={{ scale: 3.2, opacity: 0, rotate: -22 }} animate={{ scale: 1, opacity: 1, rotate: -8 }}
    transition={{ type: 'spring', stiffness: 520, damping: 26, mass: 1.1, delay }}>
    <span className="stamp-label">{label}</span>
    <span className="stamp-sub">{sub}</span>
  </motion.div>
}

/** Black band with reversed type: the section header of the paper. */
export function Band({ children, kicker }: { children: ReactNode; kicker?: string }) {
  return <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.4 }}>
    <motion.div className="band" variants={{ hidden: { clipPath: 'inset(0 100% 0 0)' }, show: { clipPath: 'inset(0 0% 0 0)' } }}
      transition={{ duration: 1, ease: EASE }}>
      {kicker && <span className="band-kicker">{kicker}</span>}
      <span className="band-title">{children}</span>
    </motion.div>
  </motion.div>
}
