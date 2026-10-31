import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { SAMPLE_DEBRIEF } from './sample'

describe('sample debrief', () => {
  it('matches the backend seed so replay recordings hit', () => {
    const seed = readFileSync(fileURLToPath(new URL('../../../backend/seed/simple.txt', import.meta.url)), 'utf8')
    expect(SAMPLE_DEBRIEF).toBe(seed.trim())
  })
})
