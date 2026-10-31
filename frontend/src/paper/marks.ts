import type { Correction } from '@/types'

export interface Mark { kind: Correction['kind']; original: string; resolved: string }
export interface Segment { text: string; mark?: Mark }

const PRIORITY: Record<Correction['kind'], number> = { digression: 0, self_correction: 1, date_resolution: 2, filler: 3 }
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Find a correction's spoken words in the raw text, tolerating case, quotes and edge punctuation. */
function locate(raw: string, original: string): [number, number] | null {
  const lower = raw.toLowerCase()
  const candidates = [original, original.replace(/^["'“‘\s]+|["'”’.,;:!?\s]+$/g, '')]
  for (const c of candidates) {
    const needle = c.trim().toLowerCase()
    if (needle.length < 2) continue
    const at = lower.indexOf(needle)
    if (at >= 0) return [at, at + needle.length]
  }
  return null
}

/**
 * Split the raw debrief into plain and marked segments so the UI can show the editor's pencil:
 * fillers struck through, digressions cut, self-corrections replaced, dates resolved.
 * Overlaps are settled by priority (a digression swallows the fillers inside it).
 */
export function markTranscript(raw: string, corrections: Correction[]): Segment[] {
  const ranges: { start: number; end: number; mark: Mark }[] = []
  for (const c of corrections) {
    const mark = { kind: c.kind, original: c.original, resolved: c.resolved }
    if (c.kind === 'filler') {
      for (const word of c.original.split(/[,;]\s*/).map((w) => w.trim()).filter(Boolean)) {
        for (const m of raw.matchAll(new RegExp(`\\b${escape(word)}\\b`, 'gi'))) {
          ranges.push({ start: m.index, end: m.index + m[0].length, mark: { ...mark, original: m[0] } })
        }
      }
      continue
    }
    const at = locate(raw, c.original)
    if (at) ranges.push({ start: at[0], end: at[1], mark })
  }
  ranges.sort((a, b) => PRIORITY[a.mark.kind] - PRIORITY[b.mark.kind] || a.start - b.start)
  const kept: typeof ranges = []
  for (const r of ranges) if (!kept.some((k) => r.start < k.end && k.start < r.end)) kept.push(r)
  kept.sort((a, b) => a.start - b.start)

  const out: Segment[] = []
  let cursor = 0
  for (const r of kept) {
    if (r.start > cursor) out.push({ text: raw.slice(cursor, r.start) })
    out.push({ text: raw.slice(r.start, r.end), mark: r.mark })
    cursor = r.end
  }
  if (cursor < raw.length) out.push({ text: raw.slice(cursor) })
  return out
}

/** "Wednesday 2026-11-04" → "Wed 4 Nov"; falls back to the text as given. */
export function shortDate(text: string): string {
  const iso = text.match(/\d{4}-\d{2}-\d{2}/)?.[0]
  if (!iso) return text
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
    .format(new Date(`${iso}T12:00:00Z`)).replace(',', '')
}

export function longDate(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${iso.slice(0, 10)}T12:00:00Z`)).replace(',', '')
}

export function topicLabel(key: string): string {
  const known: Record<string, string> = { platform_scope: 'Platform', launch_date: 'Launch', payments_provider: 'Payments' }
  return known[key] ?? key.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
}
