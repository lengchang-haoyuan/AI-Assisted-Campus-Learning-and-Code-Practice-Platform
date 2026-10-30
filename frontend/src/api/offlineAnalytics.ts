import { apiClient } from './client'
import type {
  OfflineBatchDetail,
  OfflineBatchFilters,
  OfflineBatchInfo,
  OfflineBatchPage,
  OfflineAdviceReference,
  OfflinePracticeSummary,
  OfflineRecommendation,
  RecommendationApplicationInput,
  RecommendationApplicationResponse,
} from '@/types/offlineAnalytics'

export class OfflineAnalyticsCompatibilityError extends Error {
  constructor(message = '该批次的数据口径暂不支持，请选择兼容批次或联系维护者') {
    super(message)
    this.name = 'OfflineAnalyticsCompatibilityError'
  }
}

function requireSupportedBatch(batch: OfflineBatchInfo): void {
  const legacy = batch.schema_version === 'scholarhub-source-1.0'
    && batch.metric_version === 'learning-process-1.0' && batch.rule_version === 'quality-1.0'
  const practice = batch.schema_version === 'scholarhub-source-2.0'
    && batch.metric_version === 'learning-process-2.0' && batch.rule_version === 'quality-2.0'
  if ((!legacy && !practice)
    || batch.business_timezone !== 'Asia/Shanghai'
    || !['business', 'controlled'].includes(batch.dataset_kind)) {
    throw new OfflineAnalyticsCompatibilityError()
  }
}

function requireShape(condition: unknown): asserts condition {
  if (!condition) throw new OfflineAnalyticsCompatibilityError('实践摘要或建议引用格式不符，暂不展示该结果')
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
const uuid = (value: unknown): value is string => typeof value === 'string'
  && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value)
const count = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const positive = (value: unknown): value is number => count(value) && value > 0
const nullable = (value: unknown, test: (item: unknown) => boolean): boolean => value === null || test(value)
const bool = (value: unknown): value is boolean => typeof value === 'boolean'
const criterion = (value: unknown): boolean => typeof value === 'string' && /^C0[1-6]$/.test(value)
const issue = (value: unknown): boolean => typeof value === 'string' && [
  'missing_header_validation', 'row_validation', 'csv_quoting', 'counting', 'zero_as_missing',
  'unknown_as_known', 'sum_error', 'empty_result_contract', 'external_io',
].includes(value)
const instant = (value: unknown): boolean => typeof value === 'string' && Number.isFinite(Date.parse(value))
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0

function requireAdvice(value: unknown): asserts value is OfflineAdviceReference {
  requireShape(isRecord(value) && uuid(value.attempt_id) && positive(value.attempt_no)
    && uuid(value.operation_id) && positive(value.ai_request_id) && uuid(value.review_event_id)
    && uuid(value.issue_event_id) && criterion(value.criterion_id) && issue(value.issue_type)
    && nullable(value.prompt_version, item => typeof item === 'string') && value.source === 'ai_report')
}

function requirePractice(value: unknown): asserts value is OfflinePracticeSummary {
  requireShape(isRecord(value) && value.semantics === 'advisory_process'
    && value.cohort_rule === 'sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff'
    && value.coverage_basis === 'first_retained_owner_event'
    && nullable(value.observed_event_coverage_start, instant)
    && nullable(value.teacher_confirmation_count, count)
    && Array.isArray(value.sessions) && value.sessions.length <= 500)
  for (const name of ['session_count', 'attempt_count', 'submission_event_count', 'no_submission_count', 'personal_end_count', 'request_count', 'cancel_count', 'resume_count']) {
    requireShape(count(value[name]))
  }
  for (const session of value.sessions) {
    requireShape(isRecord(session) && uuid(session.session_id) && positive(session.project_id)
      && session.template_id === 'python-learning-csv' && session.template_version === '1.0'
      && positive(session.context_version) && positive(session.revision) && instant(session.created_at)
      && ['understand', 'implement'].includes(String(session.current_step_key))
      && ['ready', 'running', 'waiting_submission', 'waiting_revision', 'waiting_confirmation', 'failed', 'cancelled', 'completed'].includes(String(session.status))
      && count(session.attempt_count) && isRecord(session.event_counts)
      && Object.keys(session.event_counts).length <= 20 && Object.values(session.event_counts).every(count)
      && nullable(session.latest_attempt_id, uuid) && nullable(session.latest_attempt_no, positive)
      && nullable(session.latest_operation_id, uuid) && nullable(session.latest_ai_request_id, positive)
      && bool(session.personal_reviewed) && nullable(session.self_statement, bool)
      && nullable(session.teacher_confirmation, bool)
      && ['matched', 'mismatched', 'unknown'].includes(String(session.output_comparison))
      && Array.isArray(session.advice) && session.advice.length <= 600)
    session.advice.forEach(requireAdvice)
  }
  requireShape(value.sessions.length === value.session_count)
}

function requireRecommendation(value: unknown): asserts value is OfflineRecommendation {
  requireShape(isRecord(value) && text(value.candidate_key) && value.candidate_key.length <= 255
    && value.rule_version === 'B-R1-advisory-1.0' && value.source === 'ai_report'
    && uuid(value.session_id) && positive(value.project_id) && value.template_id === 'python-learning-csv'
    && value.template_version === '1.0' && positive(value.context_version) && positive(value.session_revision)
    && uuid(value.attempt_id) && positive(value.attempt_no) && criterion(value.criterion_id) && issue(value.issue_type)
    && text(value.title) && text(value.explanation) && Array.isArray(value.references)
    && value.references.length >= 2 && value.references.length <= 100)
  value.references.forEach(requireAdvice)
  requireShape(new Set(value.references.map(ref => ref.attempt_id)).size >= 2
    && value.references.every(ref => ref.criterion_id === value.criterion_id && ref.issue_type === value.issue_type))
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
  const teaching = data.schema_version === 'scholarhub-source-2.0' ? data.topic_summary.teaching : data.topic_summary
  requireShape(isRecord(teaching))
  const { first_review_wait_sum_minutes: _wait, ...topicCounts } = teaching
  requireSafeCounts(topicCounts)
  if (data.schema_version === 'scholarhub-source-2.0') {
    requirePractice(data.topic_summary.practice)
    requireShape(Array.isArray(data.recommendations))
    data.recommendations.forEach(requireRecommendation)
  }
  data.daily.forEach(requireSafeCounts)
  return data
}

export async function applyOfflineRecommendation(
  batchId: string,
  input: RecommendationApplicationInput,
): Promise<RecommendationApplicationResponse> {
  const { data } = await apiClient.post<RecommendationApplicationResponse>(
    `/offline-analytics/batches/${encodeURIComponent(batchId)}/recommendation-applications`, input,
  )
  requireShape(uuid(data.application_id) && positive(data.task_id) && data.batch_id === batchId
    && data.candidate_key === input.candidate_key && typeof data.replayed === 'boolean'
    && typeof data.source_url === 'string')
  return data
}
