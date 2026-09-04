import { apiClient } from './client'
import type {
  LearningReportCreateInput,
  LearningReportListResponse,
  LearningReportResponse,
  ProjectStatisticsResponse,
  TechnologyStatisticsResponse,
  TodayStatisticsResponse,
  TrendDays,
  TrendStatisticsResponse,
} from '@/types/analytics'

export async function getTodayStatistics(
  timezoneOffsetMinutes: number,
): Promise<TodayStatisticsResponse> {
  const response = await apiClient.get<TodayStatisticsResponse>('/statistics/today', {
    params: { timezone_offset_minutes: timezoneOffsetMinutes },
  })
  return response.data
}

export async function getTrendStatistics(
  days: TrendDays,
  timezoneOffsetMinutes: number,
): Promise<TrendStatisticsResponse> {
  const response = await apiClient.get<TrendStatisticsResponse>('/statistics/trend', {
    params: { days, timezone_offset_minutes: timezoneOffsetMinutes },
  })
  return response.data
}

export async function getProjectStatistics(
  days: TrendDays,
  timezoneOffsetMinutes: number,
): Promise<ProjectStatisticsResponse> {
  const response = await apiClient.get<ProjectStatisticsResponse>('/statistics/projects', {
    params: { days, timezone_offset_minutes: timezoneOffsetMinutes },
  })
  return response.data
}

export async function getTechnologyStatistics(): Promise<TechnologyStatisticsResponse> {
  const response = await apiClient.get<TechnologyStatisticsResponse>('/statistics/tech-stacks')
  return response.data
}

export async function listLearningReports(): Promise<LearningReportListResponse> {
  const response = await apiClient.get<LearningReportListResponse>('/learning-reports', {
    params: { page: 1, page_size: 20 },
  })
  return response.data
}

export async function generateLearningReport(
  input: LearningReportCreateInput,
): Promise<LearningReportResponse> {
  // 覆盖后端 AI 总超时上限 180 秒，并预留响应持久化时间；普通请求仍为 5 秒。
  const response = await apiClient.post<LearningReportResponse>('/learning-reports', input, {
    timeout: 190_000,
  })
  return response.data
}
