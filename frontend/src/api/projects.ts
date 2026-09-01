import { apiClient } from './client'
import type {
  ProjectCreateInput,
  ProjectListQuery,
  ProjectListResponse,
  ProjectResponse,
  ProjectUpdateInput,
} from '@/types/project'

export async function listProjects(query: ProjectListQuery): Promise<ProjectListResponse> {
  const response = await apiClient.get<ProjectListResponse>('/projects', {
    params: { page: query.page, page_size: query.pageSize },
  })
  return response.data
}

export async function createProject(input: ProjectCreateInput): Promise<ProjectResponse> {
  const response = await apiClient.post<ProjectResponse>('/projects', input)
  return response.data
}

export async function getProject(projectId: number): Promise<ProjectResponse> {
  const response = await apiClient.get<ProjectResponse>(`/projects/${projectId}`)
  return response.data
}

export async function updateProject(
  projectId: number,
  input: ProjectUpdateInput,
): Promise<ProjectResponse> {
  const response = await apiClient.put<ProjectResponse>(`/projects/${projectId}`, input)
  return response.data
}

export async function deleteProject(projectId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}`)
}
