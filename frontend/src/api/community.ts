import { apiClient } from './client'
import type {
  CommentPageResponse,
  CommentResponse,
  CommunityProjectPageResponse,
  CommunityProjectListQuery,
  CommunityProjectResponse,
  GovernanceCasePageResponse,
  GovernanceCaseResponse,
  GovernanceCaseStatus,
  InteractionResponse,
  PublicationPageResponse,
  PublicationRequestInput,
  PublicationResponse,
  TagSummaryResponse,
  ViewResponse,
} from '@/types/community'

export async function listCommunityProjects(query: CommunityProjectListQuery = {}): Promise<CommunityProjectPageResponse> {
  return (await apiClient.get<CommunityProjectPageResponse>('/community/projects', { params: { page: query.page ?? 1, page_size: query.pageSize ?? 12, tag: query.tag } })).data
}

export async function getCommunityProject(projectId: number): Promise<CommunityProjectResponse> {
  return (await apiClient.get<CommunityProjectResponse>(`/community/projects/${projectId}`)).data
}

export async function listCommunityTags(): Promise<TagSummaryResponse[]> {
  return (await apiClient.get<TagSummaryResponse[]>('/community/tags')).data
}

export async function listProjectComments(projectId: number, page = 1, pageSize = 20): Promise<CommentPageResponse> {
  return (await apiClient.get<CommentPageResponse>(`/projects/${projectId}/comments`, { params: { page, page_size: pageSize } })).data
}

export async function createProjectComment(projectId: number, content: string): Promise<CommentResponse> {
  return (await apiClient.post<CommentResponse>(`/projects/${projectId}/comments`, { content })).data
}

export async function deleteProjectComment(commentId: number): Promise<void> {
  await apiClient.delete(`/comments/${commentId}`)
}

export const deleteComment = deleteProjectComment

export async function setProjectLike(projectId: number, active: boolean): Promise<InteractionResponse> {
  return (await apiClient.request<InteractionResponse>({ method: active ? 'POST' : 'DELETE', url: `/projects/${projectId}/like` })).data
}

export async function setProjectFavorite(projectId: number, active: boolean): Promise<InteractionResponse> {
  return (await apiClient.request<InteractionResponse>({ method: active ? 'POST' : 'DELETE', url: `/projects/${projectId}/favorite` })).data
}

export async function recordProjectView(projectId: number): Promise<ViewResponse> {
  return (await apiClient.post<ViewResponse>(`/projects/${projectId}/view`)).data
}

export async function getProjectPublication(projectId: number): Promise<PublicationResponse> {
  return (await apiClient.get<PublicationResponse>(`/projects/${projectId}/publication`)).data
}

export async function requestProjectPublication(projectId: number, input: PublicationRequestInput): Promise<PublicationResponse> {
  return (await apiClient.post<PublicationResponse>(`/projects/${projectId}/publication-requests`, input)).data
}

export async function withdrawPublication(publicationId: number, expectedRevision: number, reason: string): Promise<PublicationResponse> {
  return (await apiClient.post<PublicationResponse>(`/community/publications/${publicationId}/withdraw`, { expected_revision: expectedRevision, reason })).data
}

export async function listMyPublications(page = 1): Promise<PublicationPageResponse> {
  return (await apiClient.get<PublicationPageResponse>('/community/publications/mine', { params: { page, page_size: 20 } })).data
}

export async function listModerationPublications(page = 1): Promise<PublicationPageResponse> {
  return (await apiClient.get<PublicationPageResponse>('/community/moderation/publications', { params: { page, page_size: 20 } })).data
}

export async function decidePublication(publicationId: number, expectedRevision: number, decision: 'approve' | 'return' | 'take_down', reason: string): Promise<PublicationResponse> {
  return (await apiClient.post<PublicationResponse>(`/community/moderation/publications/${publicationId}/decisions`, { expected_revision: expectedRevision, decision, reason })).data
}

export async function reportCommunityContent(targetType: 'project' | 'comment', targetId: number, reason: string, requestKey: string): Promise<GovernanceCaseResponse> {
  return (await apiClient.post<GovernanceCaseResponse>('/community/reports', { request_key: requestKey, target_type: targetType, target_id: targetId, reason })).data
}

export async function listGovernanceCases(page = 1, status?: GovernanceCaseStatus): Promise<GovernanceCasePageResponse> {
  return (await apiClient.get<GovernanceCasePageResponse>('/community/governance/cases', { params: { page, page_size: 20, status } })).data
}

export async function appealGovernanceAction(actionId: number, reason: string, requestKey: string): Promise<GovernanceCaseResponse> {
  return (await apiClient.post<GovernanceCaseResponse>(`/community/moderation/actions/${actionId}/appeals`, { request_key: requestKey, reason })).data
}

export async function decideGovernanceCase(caseId: number, expectedRevision: number, decision: 'accept' | 'reject', reason: string): Promise<GovernanceCaseResponse> {
  return (await apiClient.post<GovernanceCaseResponse>(`/community/moderation/cases/${caseId}/decisions`, { expected_revision: expectedRevision, decision, reason })).data
}
