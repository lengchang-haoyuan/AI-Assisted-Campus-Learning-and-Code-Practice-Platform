export type OfflineDatasetKind = 'business' | 'controlled'
export type OfflineEmptyReason = 'no_completed_batch' | 'no_matching_batch' | 'page_empty'

export interface OfflineRatio {
  numerator: number
  denominator: number
  percent: string | null
  display: string
}

export interface OfflineRecordsSummary {
  valid_unique_rows: number
  known_minutes: number
  known_duration_count: number
  missing_duration_count: number
  known_zero_count: number
  active_days: number
  trusted_teaching_count: number
  unverified_claim_count: number
  ordinary_count: number
  raw_rows: number
  exact_duplicates: number
}

export interface OfflineTasksSummary {
  total: number
  completed: number
  cancelled: number
  overdue_unfinished: number
  completion_rate: OfflineRatio
}

export interface OfflineTopicSummary {
  cohort_count: number
  revised_count: number
  confirmed_count: number
  returned_ever_count: number
  first_pass_confirmed_count: number
  revised_confirmed_count: number
  pending_latest_count: number
  revision_attempts: number
  first_review_covered: number
  first_review_wait_sum_minutes: number
  first_review_wait_mean_minutes: string | null
  missing_teaching_record_links: number
  revised_rate: OfflineRatio
  confirmation_rate: OfflineRatio
  revised_confirmation_rate: OfflineRatio
  first_review_histogram: Record<string, number>
}

export interface OfflineDailyMetric {
  metric_date: string
  records: number
  known_minutes: number
  known_duration_count: number
  missing_duration_count: number
  known_zero_count: number
  ordinary_count: number
  trusted_teaching_count: number
  unverified_claim_count: number
  task_total: number
  completed: number
  cancelled: number
  overdue_unfinished: number
  cohort_count: number
  revised_count: number
  confirmed_count: number
}

export interface OfflineBatchInfo {
  batch_id: string
  dataset_kind: OfflineDatasetKind
  period_start: string
  period_end: string
  business_timezone: string
  source_cutoff: string
  schema_version: string
  metric_version: string
  rule_version: string
  published_at: string
}

export interface OfflineBatchPage {
  items: OfflineBatchInfo[]
  total: number
  page: number
  page_size: number
  empty_reason: OfflineEmptyReason | null
}

export interface OfflineBatchDetail extends OfflineBatchInfo {
  source: Record<string, string>
  records_summary: OfflineRecordsSummary
  tasks_summary: OfflineTasksSummary
  topic_summary: OfflineTopicSummary
  quality: Record<string, number | boolean>
  daily: OfflineDailyMetric[]
}

export interface OfflineBatchFilters {
  dataset_kind: OfflineDatasetKind
  page: number
  page_size: number
  period_start?: string
  period_end?: string
}
