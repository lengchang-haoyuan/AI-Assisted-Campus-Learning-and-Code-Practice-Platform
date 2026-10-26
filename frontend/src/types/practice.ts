import type { JsonObject } from '@/types/workflow'

export type PracticeStatus = 'ready' | 'running' | 'waiting_submission' | 'waiting_revision' | 'waiting_confirmation' | 'failed' | 'cancelled' | 'completed'
export type PracticeAction = 'start' | 'hint' | 'explain' | 'review' | 'continue' | 'cancel' | 'resume' | 'confirm'
export interface PracticeGuidance { summary: string; guidance: string[]; checks: string[] }
export interface PracticeCriterion {
  criterion_id: string
  verdict: 'pass' | 'fail' | 'unknown'
  issue_type: string | null
  evidence_span: string | null
  reason: string
  suggested_self_test: string | null
  next_action: string | null
}
export interface PracticeReview {
  summary: string
  overall: 'pass' | 'needs_changes' | 'insufficient'
  criteria: PracticeCriterion[]
  attempt_id: string
  attempt_no: number
  template_version: string
  context_version: number
}
export interface PracticeFeedback {
  schema_version: string
  binding: { attempt_id: string; attempt_no: number; template_version: string; context_version: number; submitted_revision: number }
  self_statement: { source: string; value: boolean | null }
  submitted_output_match: { source: string; matched: boolean; checks: { test_id: string; matched: boolean }[]; code_executed: false }
  ai_static_review: { source: string; ai_request_id: number; operation_id: string; review: PracticeReview; code_executed: false } | null
  personal_confirmation: { source: string; actor_user_id: number; confirmed_at: string; ai_request_id: number | null; criteria: JsonObject[] } | null
  teacher_confirmation: JsonObject | null
  review_error?: { source: string; code: string; ai_request_id: number }
}
export interface PracticeAttempt {
  id: string
  attempt_no: number
  step_key: 'implement'
  status: string
  code: string
  declared_output: JsonObject
  self_statement: boolean | null
  feedback: PracticeFeedback
  ai_request_id: number | null
  operation_id: string | null
  review_schema_version: string | null
  is_current: boolean
  candidate_stale: boolean
  can_confirm: boolean
  created_at: string
  reviewed_at: string | null
}
export interface PracticeTemplate {
  template_id: string
  template_version: string
  title: string
  function_signature: string
  task: string
  output_fields: string[]
  output_contract: Record<string, string>
  criteria: { criterion_id: string; name: string; issue_types: string[] }[]
  public_output_vectors: { test_id: string; input_csv: string; expected: JsonObject }[]
  steps: { step_key: 'understand' | 'implement'; title: string; goal: string }[]
}
export interface PracticeSession {
  id: string
  owner_user_id: number
  project_id: number
  template_id: string
  template_version: string
  context_version: number
  context_snapshot: { version: number; values: JsonObject }
  current_step_key: 'understand' | 'implement'
  status: PracticeStatus
  revision: number
  template: PracticeTemplate
  attempts: PracticeAttempt[]
  current_attempt: PracticeAttempt | null
  outputs: Record<string, PracticeGuidance | PracticeReview>
  active_result: PracticeGuidance | PracticeReview | null
  active_action: string | null
  model_request: { id: number; status: string; provider: string; model: string; error_code: string | null; prompt_tokens: number | null; completion_tokens: number | null; latency_ms: number | null } | null
  created_at: string
  updated_at: string
  replayed: boolean
  detached: boolean
}
export interface PracticeSubmission {
  expected_revision: number
  step_key: 'implement'
  request_key: string
  code: string
  declared_output: JsonObject
  self_statement: boolean | null
}
