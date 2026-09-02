export type TrendDays = 7 | 30

export interface TodayStatisticsResponse {
  date: string
  timezone_offset_minutes: number
  visitors: number
  completed_task_users: number
  project_total: number
  published_project_total: number
  projects_created: number
  projects_published: number
  community_interactions: number
}

export interface TrendPointResponse {
  date: string
  visitors: number
  completed_task_users: number
  completed_tasks: number
  projects_created: number
  projects_completed: number
  projects_published: number
  community_interactions: number
}

export interface TrendStatisticsResponse {
  days: TrendDays
  start_date: string
  end_date: string
  timezone_offset_minutes: number
  items: TrendPointResponse[]
}

export type ProjectStatus =
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'published'
  | 'archived'

export interface ProjectStatusCountResponse {
  status: ProjectStatus
  count: number
}

export interface DailyCountResponse {
  date: string
  count: number
}

export interface ProjectStatisticsResponse {
  days: TrendDays
  total: number
  published: number
  completed: number
  average_progress: number
  statuses: ProjectStatusCountResponse[]
  completion_trend: DailyCountResponse[]
}

export type TechnologyDimensionKey =
  | 'language'
  | 'framework'
  | 'frontend'
  | 'backend'
  | 'database'

export interface TechnologyItemResponse {
  name: string
  count: number
  percentage: number
}

export interface TechnologyDimensionResponse {
  key: TechnologyDimensionKey
  label: string
  items: TechnologyItemResponse[]
}

export interface TechnologyStatisticsResponse {
  total_projects: number
  dimensions: TechnologyDimensionResponse[]
}

export type LearningReportStatus = 'pending' | 'completed' | 'failed'

export interface LearningReportStructuredData {
  performance_level: 'starting' | 'steady' | 'strong' | 'excellent'
  total_learning_minutes: number
  active_days: number
  task_completion_rate: number
  project_average_progress: number
  workflow_success_rate: number
  ai_request_count: number
  focus_areas: string[]
  recommended_weekly_minutes: number
}

export interface LearningReportError {
  code: string
  message: string
}

export interface LearningReportResponse {
  id: number
  period_start: string
  period_end: string
  status: LearningReportStatus
  summary: string | null
  achievement: string[]
  problems: string[]
  suggestions: string[]
  structured_data: LearningReportStructuredData | null
  error: LearningReportError | null
  generated_at: string | null
  created_at: string
  updated_at: string
}

export interface LearningReportListResponse {
  items: LearningReportResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface LearningReportCreateInput {
  period_start: string
  period_end: string
  timezone_offset_minutes: number
}
