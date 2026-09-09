import type { ProjectDifficulty, ProjectStatus } from './project'

export const TASK_PRIORITIES = ['low', 'medium', 'high'] as const
export type TaskPriority = (typeof TASK_PRIORITIES)[number]

export const TASK_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled'] as const
export type TaskStatus = (typeof TASK_STATUSES)[number]

export const RECORD_TYPES = ['study', 'project', 'workflow', 'ai', 'course', 'task'] as const
export type RecordType = (typeof RECORD_TYPES)[number]

export interface WorkspaceProjectRef {
  id: number
  name: string
}

export interface TaskResponse {
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
  project: WorkspaceProjectRef | null
  created_at: string
  updated_at: string
}

export interface TaskCreateInput {
  title: string
  description: string | null
  priority: TaskPriority
  scheduled_date: string
  start_time: string | null
  end_time: string | null
  estimated_minutes: number | null
  project_id: number | null
}

export interface TaskListResponse {
  items: TaskResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface LearningRecordResponse {
  id: number
  title: string
  content: string | null
  record_type: RecordType
  duration_minutes: number | null
  occurred_at: string
  project: WorkspaceProjectRef | null
  created_at: string
}

export interface LearningRecordCreateInput {
  title: string
  content: string | null
  record_type: RecordType
  duration_minutes: number
  project_id: number | null
  occurred_at: string | null
}

export interface LearningRecordListResponse {
  items: LearningRecordResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface WorkspaceProjectResponse {
  id: number
  name: string
  description: string | null
  difficulty: ProjectDifficulty
  status: ProjectStatus
  language: string | null
  progress: number
  linked_task_count: number
  completed_task_count: number
  recorded_minutes: number
  updated_at: string
}

export interface WorkspaceProjectListResponse {
  items: WorkspaceProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface WorkspaceProjectDetailResponse extends WorkspaceProjectResponse {
  recent_tasks: TaskResponse[]
  recent_records: LearningRecordResponse[]
}

export interface WorkspaceStatsResponse {
  today_task_total: number
  today_task_completed: number
  today_estimated_minutes: number
  today_recorded_minutes: number
  learning_progress: number
  project_total: number
  active_project_total: number
}

export interface WorkspaceDashboardResponse {
  date: string
  stats: WorkspaceStatsResponse
  today_tasks: TaskResponse[]
  recent_projects: WorkspaceProjectResponse[]
  recent_records: LearningRecordResponse[]
}

export interface PageQuery {
  page: number
  pageSize: number
}
