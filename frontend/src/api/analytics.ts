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
  const response = await apiClient.post<LearningReportResponse>('/learning-reports', input)
  return response.data
}
