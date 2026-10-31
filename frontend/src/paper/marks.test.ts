import { describe, expect, it } from 'vitest'
import { markTranscript, shortDate } from './marks'

const raw = 'okay so um the launch moves to, uh, December 1st, no wait, November 28th. oh and the coffee machine is broken, like again. Ananya by next Wednesday.'

describe('markTranscript', () => {
  const segments = markTranscript(raw, [
    { kind: 'filler', original: 'um, uh, so, like', resolved: '' },
    { kind: 'self_correction', original: 'December 1st, no wait, November 28th', resolved: 'November 28th (2026-11-28)' },
    { kind: 'date_resolution', original: 'November 28th', resolved: 'Saturday 2026-11-28' },
    { kind: 'digression', original: 'oh and the coffee machine is broken, like again.', resolved: '' },
    { kind: 'date_resolution', original: 'next Wednesday', resolved: 'Wednesday 2026-11-04' },
  ])

  it('keeps every character of the original', () => {
    expect(segments.map((s) => s.text).join('')).toBe(raw)
  })

  it('lets a digression swallow the fillers inside it and a self-correction swallow its date', () => {
    const marked = segments.filter((s) => s.mark).map((s) => [s.mark!.kind, s.text])
    expect(marked).toEqual([
      ['filler', 'so'], ['filler', 'um'], ['filler', 'uh'],
      ['self_correction', 'December 1st, no wait, November 28th'],
      ['digression', 'oh and the coffee machine is broken, like again.'],
      ['date_resolution', 'next Wednesday'],
    ])
  })

  it('ignores corrections it cannot find', () => {
    expect(markTranscript('hello', [{ kind: 'digression', original: 'nowhere', resolved: '' }])).toEqual([{ text: 'hello' }])
  })
})

describe('shortDate', () => {
  it('formats the ISO date inside a resolution', () => {
    expect(shortDate('Wednesday 2026-11-04')).toBe('Wed 4 Nov')
    expect(shortDate('soon')).toBe('soon')
  })
})
