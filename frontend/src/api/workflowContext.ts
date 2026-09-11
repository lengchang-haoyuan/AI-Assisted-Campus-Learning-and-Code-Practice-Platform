import axios from 'axios'

import { apiClient } from './client'
import type {
  ProjectContextMutationResponse,
  ProjectContextPatch,
  ProjectContextResponse,
} from '@/types/ai'

export async function findProjectContext(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectContextResponse | null> {
  try {
    const response = await apiClient.get<ProjectContextResponse>(`/projects/${projectId}/context`, { signal })
    return response.data
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

export async function createProjectContext(projectId: number): Promise<ProjectContextResponse> {
  const response = await apiClient.post<ProjectContextResponse>(`/projects/${projectId}/context`)
  return response.data
}

export async function updateProjectContext(
  projectId: number,
  expectedVersion: number,
  values: ProjectContextPatch,
): Promise<ProjectContextMutationResponse> {
  const response = await apiClient.put<ProjectContextMutationResponse>(`/projects/${projectId}/context`, {
    expected_version: expectedVersion,
    values,
  })
  return response.data
}
