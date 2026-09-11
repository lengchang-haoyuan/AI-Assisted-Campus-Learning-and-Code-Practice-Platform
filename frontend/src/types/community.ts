import type { ProjectDifficulty, ProjectStatus } from './project'

export type PublicationKind = 'work' | 'practice_template'
export type PublicationStatus = 'legacy_review_required' | 'pending_review' | 'approved' | 'returned' | 'withdrawn' | 'taken_down'
export type GovernanceActionType = 'apply' | 'approve' | 'return' | 'withdraw' | 'take_down' | 'restore' | 'hide_comment' | 'restore_comment'
export type GovernanceCaseType = 'report' | 'appeal'
export type GovernanceCaseStatus = 'pending' | 'accepted' | 'rejected'

export interface TagResponse {
  id: number
  name: string
  slug: string
}

export interface TagSummaryResponse extends TagResponse {
  project_count: number
}

export interface CommunityProjectResponse {
  id: number
  publication_id: number
  publication_kind: PublicationKind
  publication_status: PublicationStatus
  publication_version: number
  name: string
  description: string | null
  difficulty: ProjectDifficulty
  status: ProjectStatus
  language: string | null
  framework: string | null
  frontend: string | null
  backend: string | null
  database: string | null
  repository_url: string | null
  attribution: string | null
  source_license_statement: string | null
  ai_assistance_statement: string | null
  human_review_statement: string | null
  owner: { id: number; username: string; avatar_url: string | null }
  tags: TagResponse[]
  published_at: string
  updated_at: string
  view_count: number
  comment_count: number
  like_count: number
  favorite_count: number
  liked: boolean
  favorited: boolean
}

export interface CommunityProjectPageResponse {
  items: CommunityProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
export type CommunityProjectListResponse = CommunityProjectPageResponse

export interface CommunityProjectListQuery {
  page?: number
  pageSize?: number
  tag?: string
}

export interface CommentResponse {
  id: number
  project_id: number
  author: { id: number; username: string; avatar_url: string | null }
  content: string
  revision: number
  created_at: string
  updated_at: string
  can_delete: boolean
  can_report: boolean
}

export interface CommentPageResponse {
  items: CommentResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
export type CommentListResponse = CommentPageResponse

export interface PublicationVersionResponse {
  version_number: number
  kind: PublicationKind
  name: string
  description: string | null
  difficulty: ProjectDifficulty
  project_status: ProjectStatus
  language: string | null
  framework: string | null
  frontend: string | null
  backend: string | null
  database: string | null
  repository_url: string | null
  tags: string[]
  attribution: string | null
  source_license_statement: string | null
  ai_assistance_statement: string | null
  human_review_statement: string | null
  submitted_at: string
}

export interface GovernanceActionResponse {
  id: number
  action: GovernanceActionType
  actor_user_id: number | null
  publication_id: number | null
  publication_version_number: number | null
  comment_id: number | null
  from_status: string | null
  to_status: string
  reason: string
  occurred_at: string
}

export interface PublicationResponse {
  id: number
  project_id: number | null
  owner_user_id: number
  kind: PublicationKind
  status: PublicationStatus
  public_version_number: number | null
  pending_version_number: number | null
  revision: number
  submitted_at: string | null
  reviewed_at: string | null
  published_at: string | null
  withdrawn_at: string | null
  taken_down_at: string | null
  public_version: PublicationVersionResponse | null
  pending_version: PublicationVersionResponse | null
  actions: GovernanceActionResponse[]
}

export interface PublicationPageResponse {
  items: PublicationResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PublicationRequestInput {
  request_key: string
  expected_project_updated_at: string
  kind: PublicationKind
  tags: string[]
  attribution: string
  source_license_statement: string
  ai_assistance_statement: string
  human_review_statement?: string
}

export interface GovernanceCaseResponse {
  id: number
  case_type: GovernanceCaseType
  opened_by_user_id: number | null
  target_owner_user_id: number
  target_type: 'project' | 'comment' | 'action'
  publication_id: number | null
  publication_version_number: number | null
  comment_id: number | null
  target_action_id: number | null
  reason: string | null
  target_excerpt: string
  status: GovernanceCaseStatus
  resolution_reason: string | null
  resolved_action_id: number | null
  revision: number
  created_at: string
  resolved_at: string | null
}

export interface GovernanceCasePageResponse {
  items: GovernanceCaseResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface InteractionResponse { active: boolean; count: number }
export interface ViewResponse { view_count: number }
