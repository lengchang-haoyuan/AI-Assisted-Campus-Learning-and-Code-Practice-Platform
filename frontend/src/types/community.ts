import type { ProjectDifficulty, ProjectStatus, ProjectTagResponse } from './project'

export interface CommunityOwnerResponse {
  id: number
  username: string
  avatar_url: string | null
}

export interface CommunityProjectResponse {
  id: number
  name: string
  description: string | null
  difficulty: ProjectDifficulty
  status: ProjectStatus
  language: string | null
  framework: string | null
  frontend: string | null
  backend: string | null
  database: string | null
  owner: CommunityOwnerResponse
  tags: ProjectTagResponse[]
  published_at: string
  updated_at: string
  view_count: number
  comment_count: number
  like_count: number
  favorite_count: number
  liked: boolean
  favorited: boolean
}

export interface CommunityProjectListResponse {
  items: CommunityProjectResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CommunityProjectListQuery {
  page: number
  pageSize: number
  tag?: string
}

export interface TagSummaryResponse extends ProjectTagResponse {
  project_count: number
}

export interface CommentAuthorResponse {
  id: number
  username: string
  avatar_url: string | null
}

export interface CommentResponse {
  id: number
  project_id: number
  author: CommentAuthorResponse
  content: string
  created_at: string
  updated_at: string
  can_delete: boolean
}

export interface CommentListResponse {
  items: CommentResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface InteractionResponse {
  active: boolean
  count: number
}

export interface ViewResponse {
  view_count: number
}
