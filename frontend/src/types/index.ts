/** Quorum CONTRACT.md v1.2 (2026-10-31), owned by the backend. */
export type ISODate = string
export type SourceType = 'voice' | 'transcript' | 'audio'

export interface Correction {
  original: string
  resolved: string
  kind: 'self_correction' | 'filler' | 'digression' | 'date_resolution'
}

export interface Decision {
  id: string
  topic_key: string
  statement: string
  made_by: string
  meeting_id: string
  date: ISODate
  status: 'pending' | 'active' | 'superseded'
  superseded_by: string | null
  rationale: string | null
  source_quote: string | null
}

export interface Task {
  id: string
  title: string
  owner: string
  due_date: ISODate | null
  raw_due_phrase: string
  status: 'pending' | 'todo' | 'done'
  source_quote: string
  meeting_id: string
  tracker_url: string | null
  reminder_sent: boolean
}

export interface Conflict {
  id: string
  type: 'reversal' | 'contradiction' | 'deadline_collision' | 'overload'
  severity: 'high' | 'medium' | 'low'
  new_item_id: string
  old_decision: Decision | null
  affected_tasks: Task[]
  explanation: string
  suggested_resolution: string
}

export interface Question {
  id: string
  item_id: string
  field: 'owner' | 'due_date'
  prompt: string
}

export interface Meeting {
  id: string
  project: string
  title: string
  date: ISODate
  speaker: string
  source_type: SourceType
}

export interface ReviewPayload {
  thread_id: string
  meeting: Meeting
  raw_text: string
  clean_text: string
  corrections: Correction[]
  decisions: Decision[]
  tasks: Task[]
  conflicts: Conflict[]
  questions: Question[]
  ripples: Ripple[]
  heads_up: HeadsUp[]
}

export type AgentName = 'normalizer' | 'extractor' | 'memory_retriever' | 'conflict_detector'
  | 'ripple' | 'review_editor' | 'executor' | 'memory_writer' | 'pipeline'

export interface AgentEvent {
  type: 'agent_start' | 'agent_end' | 'review_ready' | 'error'
  agent: AgentName
  message: string
  payload?: unknown
  ts: string
  run_ms?: number
}

export interface IngestInput {
  project: string
  title: string
  date: ISODate
  speaker: string
  source_type: SourceType
  text: string
}
export type FileIngestInput = Omit<IngestInput, 'text'> & { file: File }
export interface IngestResult { thread_id: string }
export interface VoiceEditResult { review: ReviewPayload; changes: string[] }
export type Resolution = 'accept_new' | 'keep_old'
export interface ApproveInput { resolutions: Record<string, Resolution>; ripple_actions?: Record<string, 'apply' | 'skip'> }
export interface ApproveResult {
  created_tasks: Task[]
  superseded_ids: string[]
  updated_tasks: Task[]
  cancelled_task_ids: string[]
  heads_up_sent: { person: string; channel: string }[]
}
export interface OkResult { ok: boolean }

export interface Project { name: string; meeting_count: number; last_meeting: ISODate }
export interface Person { name: string; open_tasks: number; overdue: number }

export interface DecisionGraph {
  nodes: { id: string; label: string; status: Decision['status']; date: ISODate; meeting_title: string }[]
  edges: { source: string; target: string; kind: 'supersedes' }[]
}
export interface Citation { meeting_id: string; meeting_title: string; date: ISODate; quote: string }
export interface AskResult { answer: string; citations: Citation[] }
export interface Digest {
  person: string
  week_of: ISODate
  summary_md: string
  done: Task[]
  due: Task[]
  overdue: Task[]
  decisions: Decision[]
  conflicts: Conflict[]
}
export interface Clock { now: string }
export interface ReminderResult { sent: { task_id: string; owner: string; channel: string }[] }
export interface DecisionFilters { project?: string; include_superseded?: boolean }
export interface TaskFilters { project?: string; owner?: string }

export interface Ripple {
  id: string
  conflict_id: string | null
  decision_id: string
  kind: 'reschedule' | 'rescope' | 'cancel' | 'unowned_work'
  task: Task | null
  reason: string
  proposal: { title?: string; owner?: string; due_date?: ISODate | null; raw_due_phrase?: string }
  default_action: 'apply' | 'skip'
}
export interface HeadsUp { person: string; message_md: string; ripple_ids: string[]; task_ids: string[] }
export interface RadarTopic {
  topic_key: string
  label: string
  versions: number
  flips: number
  last_changed: ISODate
  churn: number
  risk: 'high' | 'medium' | 'low'
  statements: { decision_id: string; date: ISODate; statement: string; made_by: string }[]
  note: string
}
export interface Radar { project: string; topics: RadarTopic[] }
export interface DecisionSnapshot {
  project: string
  date: ISODate
  decisions: Decision[]
  changed_since: { topic_key: string; then: Decision; now: Decision }[]
}
export interface DecisionTimeline {
  topics: {
    topic_key: string
    label: string
    events: {
      decision: Decision; meeting_id: string; meeting_title: string; date: ISODate
      made_by: string; quote: string; change: 'created' | 'reversed' | 'amended'
    }[]
  }[]
}
export interface WalkInBrief {
  project: string
  as_of: string
  headline: string
  script_md: string
  agenda: string[]
  open_conflicts: Conflict[]
  overdue: Task[]
  due_soon: Task[]
  hot_topics: RadarTopic[]
}
export interface Health {
  ok: boolean; version: string; replay: boolean; clock: string
  integrations: { groq: boolean; notion: boolean; github: boolean; telegram: boolean }
}
