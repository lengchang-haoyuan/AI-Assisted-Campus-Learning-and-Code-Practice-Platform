import { apiClient } from './client'
import type {
  OfflineBatchDetail,
  OfflineBatchFilters,
  OfflineBatchInfo,
  OfflineBatchPage,
} from '@/types/offlineAnalytics'

export class OfflineAnalyticsCompatibilityError extends Error {
  constructor(message = '该批次的数据口径暂不支持，请选择兼容批次或联系维护者') {
    super(message)
    this.name = 'OfflineAnalyticsCompatibilityError'
  }
}

function requireSupportedBatch(batch: OfflineBatchInfo): void {
  if (batch.schema_version !== 'scholarhub-source-1.0'
    || batch.metric_version !== 'learning-process-1.0'
    || batch.rule_version !== 'quality-1.0'
    || batch.business_timezone !== 'Asia/Shanghai'
    || !['business', 'controlled'].includes(batch.dataset_kind)) {
    throw new OfflineAnalyticsCompatibilityError()
  }
}

function requireSafeCounts(values: object): void {
  // 后端计数支持 BIGINT；浏览器无法精确表达的整数不能作为准确事实展示。
  for (const value of Object.values(values)) {
    if (typeof value === 'number' && (!Number.isSafeInteger(value) || value < 0)) {
      throw new OfflineAnalyticsCompatibilityError('该批次计数超出浏览器的精确展示范围')
    }
  }
}

export async function listOfflineBatches(
  filters: OfflineBatchFilters,
  signal?: AbortSignal,
): Promise<OfflineBatchPage> {
  const { data } = await apiClient.get<OfflineBatchPage>('/offline-analytics/batches', {
    params: filters,
    signal,
  })
  data.items.forEach(requireSupportedBatch)
  return data
}

export async function getOfflineBatch(
  batchId: string,
  signal?: AbortSignal,
): Promise<OfflineBatchDetail> {
  const { data } = await apiClient.get<OfflineBatchDetail>(
    `/offline-analytics/batches/${encodeURIComponent(batchId)}`,
    { signal },
  )
  requireSupportedBatch(data)
  if (data.batch_id !== batchId || data.quality.fatal_errors !== 0 || data.quality.reconciled !== true) {
    throw new OfflineAnalyticsCompatibilityError('批次身份或质量校验不符，暂不展示该结果')
  }
  requireSafeCounts(data.records_summary)
  requireSafeCounts(data.tasks_summary)
  const { first_review_wait_sum_minutes: _wait, ...topicCounts } = data.topic_summary
  requireSafeCounts(topicCounts)
  data.daily.forEach(requireSafeCounts)
  return data
}
