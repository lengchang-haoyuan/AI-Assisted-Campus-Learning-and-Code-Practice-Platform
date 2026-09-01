import { apiClient } from './client'
import type {
  CommentListResponse,
  CommentResponse,
  CommunityProjectListQuery,
  CommunityProjectListResponse,
  CommunityProjectResponse,
  InteractionResponse,
  TagSummaryResponse,
  ViewResponse,
} from '@/types/community'

export async function listCommunityProjects(
  query: CommunityProjectListQuery,
): Promise<CommunityProjectListResponse> {
  const response = await apiClient.get<CommunityProjectListResponse>('/community/projects', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      ...(query.tag ? { tag: query.tag } : {}),
    },
  })
  return response.data
}

export async function getCommunityProject(projectId: number): Promise<CommunityProjectResponse> {
  const response = await apiClient.get<CommunityProjectResponse>(
    `/community/projects/${projectId}`,
  )
  return response.data
}

export async function listCommunityTags(): Promise<TagSummaryResponse[]> {
  const response = await apiClient.get<TagSummaryResponse[]>('/community/tags')
  return response.data
}

export async function publishProject(
  projectId: number,
  tags: string[],
): Promise<CommunityProjectResponse> {
  const response = await apiClient.post<CommunityProjectResponse>(`/projects/${projectId}/publish`, {
    tags,
  })
  return response.data
}

export async function unpublishProject(projectId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/publish`)
}

export async function recordProjectView(projectId: number): Promise<ViewResponse> {
  const response = await apiClient.post<ViewResponse>(`/projects/${projectId}/view`)
  return response.data
}

export async function listProjectComments(
  projectId: number,
  page: number,
  pageSize: number,
): Promise<CommentListResponse> {
  const response = await apiClient.get<CommentListResponse>(`/projects/${projectId}/comments`, {
    params: { page, page_size: pageSize },
  })
  return response.data
}

export async function createProjectComment(
  projectId: number,
  content: string,
): Promise<CommentResponse> {
  const response = await apiClient.post<CommentResponse>(`/projects/${projectId}/comments`, {
    content,
  })
  return response.data
}

export async function deleteComment(commentId: number): Promise<void> {
  await apiClient.delete(`/comments/${commentId}`)
}

export async function setProjectLike(
  projectId: number,
  active: boolean,
): Promise<InteractionResponse> {
  const response = active
    ? await apiClient.post<InteractionResponse>(`/projects/${projectId}/like`)
    : await apiClient.delete<InteractionResponse>(`/projects/${projectId}/like`)
  return response.data
}

export async function setProjectFavorite(
  projectId: number,
  active: boolean,
): Promise<InteractionResponse> {
  const response = active
    ? await apiClient.post<InteractionResponse>(`/projects/${projectId}/favorite`)
    : await apiClient.delete<InteractionResponse>(`/projects/${projectId}/favorite`)
  return response.data
}
