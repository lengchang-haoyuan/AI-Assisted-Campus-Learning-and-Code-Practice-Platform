export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export const PROJECT_DIFFICULTIES = ['beginner', 'intermediate', 'advanced'] as const
export type ProjectDifficulty = (typeof PROJECT_DIFFICULTIES)[number]

export const PROJECT_STATUSES = [
  'not_started',
  'in_progress',
  'completed',
  'published',
  'archived',
] as const
export type ProjectStatus = (typeof PROJECT_STATUSES)[number]

export interface ProjectOwnerResponse {
  id: number
  username: string
}

export interface ProjectTagResponse {
  id: number
  name: string
  slug: string
}

export interface ProjectFields {
  name: string
  description: string | null
  difficulty: ProjectDifficulty
  language: string | null
  framework: string | null
  frontend: string | null
  backend: string | null
  database: string | null
  requirements: Array<Record<string, JsonValue>> | null
  output_requirement: string | null
  status: ProjectStatus
}

export interface ProjectResponse extends ProjectFields {
  id: number
  owner: ProjectOwnerResponse
  tags: ProjectTagResponse[]
  is_published: boolean
  published_at: string | null
  view_count: number
  created_at: string
  updated_at: string
}

export interface ProjectListResponse {
  items: ProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type ProjectCreateInput = ProjectFields
export type ProjectUpdateInput = Partial<ProjectFields>

export interface ProjectListQuery {
  page: number
  pageSize: number
}
