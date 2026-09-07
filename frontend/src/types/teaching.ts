import type { JsonValue } from './project'

export type TeachingClassStatus = 'active' | 'archived'
export type ClassMemberRole = 'teacher' | 'student'
export type ClassMembershipStatus = 'active' | 'left' | 'removed'
export type TeachingAssignmentStatus = 'draft' | 'published' | 'closed' | 'archived'

export interface TeachingClassResponse {
  id: number
  name: string
  course_title: string
  term_label: string
  status: TeachingClassStatus
  revision: number
  archived_at: string | null
  created_at: string
  updated_at: string
  viewer_role: 'administrator' | ClassMemberRole
  viewer_member_id: number | null
  viewer_member_revision: number | null
  can_edit: boolean
  can_view_members: boolean
  can_manage_members: boolean
  can_create_assignments: boolean
}

export interface ClassMemberResponse {
  id: number
  campus_membership_id: number
  user_id: number
  username: string
  member_role: ClassMemberRole
  status: ClassMembershipStatus
  joined_at: string
  left_at: string | null
  revision: number
}

export interface TeachingAssignmentResponse {
  id: number
  class_id: number
  title: string
  instructions: string
  learning_objectives: string[]
  acceptance_criteria: string[]
  due_at: string | null
  status: TeachingAssignmentStatus
  source_project_snapshot: Record<string, JsonValue> | null
  revision: number
  published_at: string | null
  closed_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
  can_edit: boolean
  can_publish: boolean
  can_close: boolean
  can_archive: boolean
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TeachingClassCreateInput {
  name: string
  course_title: string
  term_label: string
}

export interface TeachingClassUpdateInput extends Partial<TeachingClassCreateInput> {
  expected_revision: number
  status?: TeachingClassStatus
}

export interface TeachingAssignmentCreateInput {
  title: string
  instructions: string
  learning_objectives: string[]
  acceptance_criteria: string[]
  due_at: string | null
  source_project_id: number | null
}

export interface TeachingAssignmentUpdateInput extends Partial<TeachingAssignmentCreateInput> {
  expected_revision: number
}
