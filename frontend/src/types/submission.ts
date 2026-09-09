import type { PageResponse } from './teaching'

export type SubmissionStatus = 'submitted' | 'returned' | 'accepted'
export type FeedbackDecision = 'accept' | 'return'
export type NotificationKind = 'assignment_published' | 'feedback_created'

export interface FeedbackResponse {
  id: number
  decision: FeedbackDecision
  comment: string
  created_at: string
}

export interface SubmissionVersionResponse {
  id: number
  version_number: number
  summary: string
  repository_url: string | null
  repository_ref: string | null
  source_project_title: string | null
  has_project_reference: boolean
  status: SubmissionStatus
  submitted_at: string
  reviewed_at: string | null
  revision: number
  feedback: FeedbackResponse | null
}

export interface SubmissionResponse {
  id: number
  class_id: number
  assignment_id: number
  assignment_title: string
  assignment_due_at: string
  student_username: string
  latest_version_number: number
  revision: number
  created_at: string
  updated_at: string
  latest_version: SubmissionVersionResponse
  can_review: boolean
  can_submit_next: boolean
  is_owner: boolean
}

export interface SubmissionCreateInput {
  request_key: string
  expected_latest_version: number
  summary: string
  repository_url: string | null
  repository_ref: string | null
  source_project_id: number | null
}

export interface NotificationResponse {
  id: number
  kind: NotificationKind
  assignment_id: number
  feedback_id: number | null
  submission_id: number | null
  created_at: string
  read_at: string | null
}

export interface PendingAssignmentResponse {
  id: number
  class_id: number
  title: string
  due_at: string
  submission_id: number | null
  current_status: SubmissionStatus | null
}

export interface NotificationPageResponse extends PageResponse<NotificationResponse> {
  unread_count: number
}

export type SubmissionPageResponse = PageResponse<SubmissionResponse>
export type SubmissionVersionPageResponse = PageResponse<SubmissionVersionResponse>
export type PendingAssignmentPageResponse = PageResponse<PendingAssignmentResponse>
