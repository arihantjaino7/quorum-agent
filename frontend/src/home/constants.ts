import type { AgentName } from '@/types'

export const EASE = [0.22, 1, 0.36, 1] as const
export const EASE_IN_OUT = [0.76, 0, 0.24, 1] as const

export const STEPS: { agent: AgentName; label: string; idle: string }[] = [
  { agent: 'normalizer', label: 'Clean up', idle: 'Fillers, digressions, dates' },
  { agent: 'extractor', label: 'Extract', idle: 'Decisions, owners, deadlines' },
  { agent: 'memory_retriever', label: 'Recall', idle: 'What the team agreed before' },
  { agent: 'conflict_detector', label: 'Cross-check', idle: 'Anything that contradicts it' },
  { agent: 'ripple', label: 'Ripple', idle: 'Work that this changes' },
]
export const AFTER: { agent: AgentName; label: string; idle: string }[] = [
  { agent: 'executor', label: 'Follow through', idle: 'Tasks and heads-ups' },
  { agent: 'memory_writer', label: 'Remember', idle: 'Update team memory' },
]

