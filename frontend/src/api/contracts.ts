import type {
  AgentEvent, ApproveInput, ApproveResult, AskResult, Clock, Decision,
  DecisionFilters, DecisionGraph, Digest, FileIngestInput, IngestInput,
  IngestResult, Meeting, OkResult, Person, Project, ReminderResult,
  ReviewPayload, Task, TaskFilters, VoiceEditResult, Health, WalkInBrief, Radar,
  DecisionSnapshot, DecisionTimeline,
} from '@/types'

export interface StreamOptions {
  onEvent: (event: AgentEvent) => void
  onError?: (error: Error) => void
  /** v1.2: keep listening through execution when resuming an approved, failed run. */
  stopAtReview?: boolean
}
export type Unsubscribe = () => void

/** One interface for real HTTP and the deterministic in-memory demo. */
export interface QuorumApi {
  ingest(input: IngestInput): Promise<IngestResult>
  ingestFile(input: FileIngestInput): Promise<IngestResult>
  streamRun(threadId: string, options: StreamOptions): Unsubscribe
  getReview(threadId: string): Promise<ReviewPayload>
  voiceEdit(threadId: string, instruction: string): Promise<VoiceEditResult>
  approve(threadId: string, input: ApproveInput): Promise<ApproveResult>
  reject(threadId: string): Promise<OkResult>
  retryRun(threadId: string): Promise<OkResult>
  getProjects(): Promise<Project[]>
  getMeetings(project?: string): Promise<Meeting[]>
  getPeople(): Promise<Person[]>
  getDecisions(filters?: DecisionFilters): Promise<Decision[]>
  getDecisionGraph(project?: string): Promise<DecisionGraph>
  getTasks(filters?: TaskFilters): Promise<Task[]>
  updateTask(taskId: string, status: 'todo' | 'done'): Promise<Task>
  ask(project: string, question: string): Promise<AskResult>
  getDigest(person: string, weekOf?: string): Promise<Digest>
  getClock(): Promise<Clock>
  setClock(now: string): Promise<Clock>
  runReminders(): Promise<ReminderResult>
  resetDemo(): Promise<void>
  getHealth(): Promise<Health>
  getBrief(project?: string): Promise<WalkInBrief>
  getRadar(project?: string): Promise<Radar>
  getDecisionsAsOf(project: string, date: string): Promise<DecisionSnapshot>
  getDecisionTimeline(project?: string, topicKey?: string): Promise<DecisionTimeline>
}
