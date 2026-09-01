import { apiClient } from './client'
import type {
  LearningRecordCreateInput,
  LearningRecordListResponse,
  LearningRecordResponse,
  PageQuery,
  TaskCreateInput,
  TaskListResponse,
  TaskResponse,
  WorkspaceDashboardResponse,
  WorkspaceProjectDetailResponse,
  WorkspaceProjectListResponse,
} from '@/types/workspace'

export async function getWorkspaceDashboard(
  selectedDate: string,
  utcOffsetMinutes: number,
): Promise<WorkspaceDashboardResponse> {
  const response = await apiClient.get<WorkspaceDashboardResponse>('/workspace/dashboard', {
    params: { date: selectedDate, utc_offset_minutes: utcOffsetMinutes },
  })
  return response.data
}

export async function listTasks(
  query: PageQuery,
  selectedDate?: string,
): Promise<TaskListResponse> {
  const response = await apiClient.get<TaskListResponse>('/workspace/tasks', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      ...(selectedDate ? { date: selectedDate } : {}),
    },
  })
  return response.data
}

export async function createTask(input: TaskCreateInput): Promise<TaskResponse> {
  const response = await apiClient.post<TaskResponse>('/workspace/tasks', input)
  return response.data
}

export async function completeTask(taskId: number): Promise<TaskResponse> {
  const response = await apiClient.post<TaskResponse>(`/workspace/tasks/${taskId}/complete`)
  return response.data
}

export async function listWorkspaceProjects(
  query: PageQuery,
): Promise<WorkspaceProjectListResponse> {
  const response = await apiClient.get<WorkspaceProjectListResponse>('/workspace/projects', {
    params: { page: query.page, page_size: query.pageSize },
  })
  return response.data
}

export async function getWorkspaceProject(
  projectId: number,
): Promise<WorkspaceProjectDetailResponse> {
  const response = await apiClient.get<WorkspaceProjectDetailResponse>(
    `/workspace/projects/${projectId}`,
  )
  return response.data
}

export async function listLearningRecords(
  query: PageQuery,
): Promise<LearningRecordListResponse> {
  const response = await apiClient.get<LearningRecordListResponse>('/workspace/records', {
    params: { page: query.page, page_size: query.pageSize },
  })
  return response.data
}

export async function createLearningRecord(
  input: LearningRecordCreateInput,
): Promise<LearningRecordResponse> {
  const response = await apiClient.post<LearningRecordResponse>('/workspace/records', input)
  return response.data
}
