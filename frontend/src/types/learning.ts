import type { JsonValue } from '@/types/project'
import type { ProjectResponse } from '@/types/project'
import type { RecordType, TaskPriority, TaskStatus } from '@/types/workspace'

export type CourseStatus = 'active' | 'completed' | 'archived'
export type LearningPlanStatus = 'draft' | 'active' | 'completed' | 'cancelled'

export interface ResourceRefResponse {
  id: number
  name: string
}

export interface CourseFields {
  name: string
  code: string | null
  description: string | null
  instructor: string | null
  schedule_data: Record<string, JsonValue> | null
  status: CourseStatus
}

export interface CourseResponse extends CourseFields {
  id: number
  created_at: string
  updated_at: string
}

export interface CourseListResponse {
  items: CourseResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type CourseCreateInput = CourseFields
export type CourseUpdateInput = Partial<CourseFields>

export interface LearningPlanFields {
  title: string
  description: string | null
  status: LearningPlanStatus
  start_date: string | null
  end_date: string | null
  goal_data: Record<string, JsonValue> | null
  project_id: number | null
  course_id: number | null
}

export interface LearningPlanResponse {
  id: number
  title: string
  description: string | null
  status: LearningPlanStatus
  start_date: string | null
  end_date: string | null
  goal_data: Record<string, JsonValue> | null
  progress: number
  project: ResourceRefResponse | null
  course: ResourceRefResponse | null
  created_at: string
  updated_at: string
}

export interface LearningPlanListResponse {
  items: LearningPlanResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type LearningPlanCreateInput = LearningPlanFields
export type LearningPlanUpdateInput = Partial<LearningPlanFields>

export interface LearningTaskFields {
  title: string
  description: string | null
  priority: TaskPriority
  scheduled_date: string
  start_time: string | null
  end_time: string | null
  estimated_minutes: number | null
  plan_id: number | null
  project_id: number | null
}

export interface LearningTaskResponse {
  id: number
  title: string
  description: string | null
  priority: TaskPriority
  status: TaskStatus
  scheduled_date: string
  start_time: string | null
  end_time: string | null
  estimated_minutes: number | null
  completed_at: string | null
  plan: ResourceRefResponse | null
  project: ResourceRefResponse | null
  created_at: string
  updated_at: string
}

export interface LearningTaskListResponse {
  items: LearningTaskResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type LearningTaskCreateInput = LearningTaskFields
export type LearningTaskUpdateInput = Partial<LearningTaskFields> & { status?: TaskStatus }

export interface LearningRecordFields {
  title: string
  content: string | null
  record_type: RecordType
  duration_minutes: number
  occurred_at: string
  project_id: number | null
  course_id: number | null
  task_id: number | null
  record_metadata: Record<string, JsonValue> | null
}

export interface LearningRecordResponse {
  id: number
  title: string
  content: string | null
  record_type: RecordType
  duration_minutes: number
  occurred_at: string
  project: ResourceRefResponse | null
  course: ResourceRefResponse | null
  task: ResourceRefResponse | null
  record_metadata: Record<string, JsonValue> | null
  created_at: string
}

export interface LearningRecordListResponse {
  items: LearningRecordResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type LearningRecordCreateInput = LearningRecordFields
export type LearningRecordUpdateInput = Partial<LearningRecordFields>

export interface LearningReferences {
  courses: CourseResponse[]
  plans: LearningPlanResponse[]
  projects: ProjectResponse[]
  tasks: LearningTaskResponse[]
}

export interface LearningPageQuery {
  page: number
  pageSize: number
}
