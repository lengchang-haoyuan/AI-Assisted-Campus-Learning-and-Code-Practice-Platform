import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  generateLearningReport,
  getProjectStatistics,
  getTechnologyStatistics,
  getTodayStatistics,
  getTrendStatistics,
  listLearningReports,
} from '@/api/analytics'
import { getApiErrorMessage } from '@/api/errors'
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

const EMPTY_REPORT_PAGE: LearningReportListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
}

export const useAnalyticsStore = defineStore('analytics', () => {
  const today = ref<TodayStatisticsResponse | null>(null)
  const trend = ref<TrendStatisticsResponse | null>(null)
  const projects = ref<ProjectStatisticsResponse | null>(null)
  const technologies = ref<TechnologyStatisticsResponse | null>(null)
  const reports = ref<LearningReportListResponse>({ ...EMPTY_REPORT_PAGE })
  const selectedReport = ref<LearningReportResponse | null>(null)
  const loading = ref(false)
  const reportLoading = ref(false)
  const generating = ref(false)
  const error = ref<string | null>(null)
  const reportError = ref<string | null>(null)
  let dashboardSequence = 0

  async function fetchDashboard(days: TrendDays, timezoneOffsetMinutes: number): Promise<void> {
    const sequence = ++dashboardSequence
    loading.value = true
    error.value = null
    try {
      const [todayResult, trendResult, projectResult, technologyResult] = await Promise.all([
        getTodayStatistics(timezoneOffsetMinutes),
        getTrendStatistics(days, timezoneOffsetMinutes),
        getProjectStatistics(days, timezoneOffsetMinutes),
        getTechnologyStatistics(),
      ])
      if (sequence !== dashboardSequence) return
      today.value = todayResult
      trend.value = trendResult
      projects.value = projectResult
      technologies.value = technologyResult
    } catch (caught: unknown) {
      if (sequence === dashboardSequence) {
        error.value = getApiErrorMessage(caught, '统计数据加载失败，请重试')
      }
      throw caught
    } finally {
      if (sequence === dashboardSequence) loading.value = false
    }
  }

  async function fetchReports(): Promise<void> {
    reportLoading.value = true
    reportError.value = null
    try {
      reports.value = await listLearningReports()
      if (selectedReport.value) {
        selectedReport.value = reports.value.items.find(
          (item) => item.id === selectedReport.value?.id,
        ) ?? reports.value.items[0] ?? null
      } else {
        selectedReport.value = reports.value.items[0] ?? null
      }
    } catch (caught: unknown) {
      reportError.value = getApiErrorMessage(caught, '学习报告加载失败，请重试')
      throw caught
    } finally {
      reportLoading.value = false
    }
  }

  async function createReport(input: LearningReportCreateInput): Promise<LearningReportResponse> {
    generating.value = true
    reportError.value = null
    try {
      const report = await generateLearningReport(input)
      selectedReport.value = report
      await fetchReports()
      return report
    } catch (caught: unknown) {
      reportError.value = getApiErrorMessage(caught, '学习报告生成失败，请重试')
      throw caught
    } finally {
      generating.value = false
    }
  }

  function selectReport(report: LearningReportResponse): void {
    selectedReport.value = report
  }

  return {
    today,
    trend,
    projects,
    technologies,
    reports,
    selectedReport,
    loading,
    reportLoading,
    generating,
    error,
    reportError,
    fetchDashboard,
    fetchReports,
    createReport,
    selectReport,
  }
})
