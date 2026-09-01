import { apiClient } from './client'
import type {
  CourseCreateInput,
  CourseListResponse,
  CourseResponse,
  CourseUpdateInput,
  LearningPageQuery,
  LearningPlanCreateInput,
  LearningPlanListResponse,
  LearningPlanResponse,
  LearningPlanUpdateInput,
  LearningRecordCreateInput,
  LearningRecordListResponse,
  LearningRecordResponse,
  LearningRecordUpdateInput,
  LearningTaskCreateInput,
  LearningTaskListResponse,
  LearningTaskResponse,
  LearningTaskUpdateInput,
} from '@/types/learning'

function pageParams(query: LearningPageQuery): { page: number; page_size: number } {
  return { page: query.page, page_size: query.pageSize }
}

export async function listCourses(query: LearningPageQuery): Promise<CourseListResponse> {
  const response = await apiClient.get<CourseListResponse>('/courses', {
    params: pageParams(query),
  })
  return response.data
}

export async function createCourse(input: CourseCreateInput): Promise<CourseResponse> {
  const response = await apiClient.post<CourseResponse>('/courses', input)
  return response.data
}

export async function updateCourse(
  courseId: number,
  input: CourseUpdateInput,
): Promise<CourseResponse> {
  const response = await apiClient.put<CourseResponse>(`/courses/${courseId}`, input)
  return response.data
}

export async function deleteCourse(courseId: number): Promise<void> {
  await apiClient.delete(`/courses/${courseId}`)
}

export async function listPlans(query: LearningPageQuery): Promise<LearningPlanListResponse> {
  const response = await apiClient.get<LearningPlanListResponse>('/learning/plans', {
    params: pageParams(query),
  })
  return response.data
}

export async function createPlan(input: LearningPlanCreateInput): Promise<LearningPlanResponse> {
  const response = await apiClient.post<LearningPlanResponse>('/learning/plans', input)
  return response.data
}

export async function updatePlan(
  planId: number,
  input: LearningPlanUpdateInput,
): Promise<LearningPlanResponse> {
  const response = await apiClient.put<LearningPlanResponse>(`/learning/plans/${planId}`, input)
  return response.data
}

export async function deletePlan(planId: number): Promise<void> {
  await apiClient.delete(`/learning/plans/${planId}`)
}

export async function listLearningTasks(
  query: LearningPageQuery,
  options: { scheduledDate?: string; planId?: number } = {},
): Promise<LearningTaskListResponse> {
  const response = await apiClient.get<LearningTaskListResponse>('/learning/tasks', {
    params: {
      ...pageParams(query),
      ...(options.scheduledDate ? { scheduled_date: options.scheduledDate } : {}),
      ...(options.planId ? { plan_id: options.planId } : {}),
    },
  })
  return response.data
}

export async function createLearningTask(
  input: LearningTaskCreateInput,
): Promise<LearningTaskResponse> {
  const response = await apiClient.post<LearningTaskResponse>('/learning/tasks', input)
  return response.data
}

export async function updateLearningTask(
  taskId: number,
  input: LearningTaskUpdateInput,
): Promise<LearningTaskResponse> {
  const response = await apiClient.put<LearningTaskResponse>(`/learning/tasks/${taskId}`, input)
  return response.data
}

export async function completeLearningTask(taskId: number): Promise<LearningTaskResponse> {
  const response = await apiClient.post<LearningTaskResponse>(
    `/learning/tasks/${taskId}/complete`,
  )
  return response.data
}

export async function deleteLearningTask(taskId: number): Promise<void> {
  await apiClient.delete(`/learning/tasks/${taskId}`)
}

export async function listLearningRecords(
  query: LearningPageQuery,
): Promise<LearningRecordListResponse> {
  const response = await apiClient.get<LearningRecordListResponse>('/learning/records', {
    params: pageParams(query),
  })
  return response.data
}

export async function createLearningRecord(
  input: LearningRecordCreateInput,
): Promise<LearningRecordResponse> {
  const response = await apiClient.post<LearningRecordResponse>('/learning/records', input)
  return response.data
}

export async function updateLearningRecord(
  recordId: number,
  input: LearningRecordUpdateInput,
): Promise<LearningRecordResponse> {
  const response = await apiClient.put<LearningRecordResponse>(
    `/learning/records/${recordId}`,
    input,
  )
  return response.data
}

export async function deleteLearningRecord(recordId: number): Promise<void> {
  await apiClient.delete(`/learning/records/${recordId}`)
}
