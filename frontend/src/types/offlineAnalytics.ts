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

interface OfflineBatchInfoFields {
  batch_id: string
  dataset_kind: OfflineDatasetKind
  period_start: string
  period_end: string
  business_timezone: string
  source_cutoff: string
  published_at: string
}

export interface OfflineBatchInfoV1 extends OfflineBatchInfoFields {
  schema_version: 'scholarhub-source-1.0'
  metric_version: 'learning-process-1.0'
  rule_version: 'quality-1.0'
}

export interface OfflineBatchInfoV2 extends OfflineBatchInfoFields {
  schema_version: 'scholarhub-source-2.0'
  metric_version: 'learning-process-2.0'
  rule_version: 'quality-2.0'
}

export type OfflineBatchInfo = OfflineBatchInfoV1 | OfflineBatchInfoV2

export interface OfflineBatchPage {
  items: OfflineBatchInfo[]
  total: number
  page: number
  page_size: number
  empty_reason: OfflineEmptyReason | null
}

interface OfflineBatchDetailFields {
  source: Record<string, string>
  records_summary: OfflineRecordsSummary
  tasks_summary: OfflineTasksSummary
  quality: Record<string, number | boolean>
  daily: OfflineDailyMetric[]
}

export type PracticeCriterionId = 'C01' | 'C02' | 'C03' | 'C04' | 'C05' | 'C06'
export type PracticeIssueType = 'missing_header_validation' | 'row_validation' | 'csv_quoting'
  | 'counting' | 'zero_as_missing' | 'unknown_as_known' | 'sum_error' | 'empty_result_contract' | 'external_io'

export interface OfflineAdviceReference {
  attempt_id: string
  attempt_no: number
  operation_id: string
  ai_request_id: number
  review_event_id: string
  issue_event_id: string
  criterion_id: PracticeCriterionId
  issue_type: PracticeIssueType
  prompt_version: string | null
  source: 'ai_report'
}

export interface OfflinePracticeSession {
  session_id: string
  project_id: number
  template_id: 'python-learning-csv'
  template_version: '1.0'
  context_version: number
  revision: number
  current_step_key: 'understand' | 'implement'
  status: import('@/types/practice').PracticeStatus
  created_at: string
  attempt_count: number
  event_counts: Record<string, number>
  latest_attempt_id: string | null
  latest_attempt_no: number | null
  latest_operation_id: string | null
  latest_ai_request_id: number | null
  personal_reviewed: boolean
  self_statement: boolean | null
  output_comparison: 'matched' | 'mismatched' | 'unknown'
  teacher_confirmation: boolean | null
  advice: OfflineAdviceReference[]
}

export interface OfflinePracticeSummary {
  semantics: 'advisory_process'
  cohort_rule: 'sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff'
  observed_event_coverage_start: string | null
  coverage_basis: 'first_retained_owner_event'
  session_count: number
  attempt_count: number
  submission_event_count: number
  no_submission_count: number
  personal_end_count: number
  request_count: number
  cancel_count: number
  resume_count: number
  teacher_confirmation_count: number | null
  sessions: OfflinePracticeSession[]
}

export interface OfflineRecommendation {
  candidate_key: string
  rule_version: 'B-R1-advisory-1.0'
  source: 'ai_report'
  session_id: string
  project_id: number
  template_id: 'python-learning-csv'
  template_version: '1.0'
  context_version: number
  session_revision: number
  attempt_id: string
  attempt_no: number
  criterion_id: PracticeCriterionId
  issue_type: PracticeIssueType
  references: OfflineAdviceReference[]
  title: string
  explanation: string
}

export interface OfflineBatchDetailV1 extends OfflineBatchInfoV1, OfflineBatchDetailFields {
  topic_summary: OfflineTopicSummary
  recommendations?: never[]
}

export interface OfflineBatchDetailV2 extends OfflineBatchInfoV2, OfflineBatchDetailFields {
  topic_summary: { teaching: OfflineTopicSummary; practice: OfflinePracticeSummary }
  recommendations: OfflineRecommendation[]
}

export type OfflineBatchDetail = OfflineBatchDetailV1 | OfflineBatchDetailV2

export interface RecommendationApplicationInput {
  request_key: string
  candidate_key: string
  expected_metric_version: 'learning-process-2.0'
  expected_rule_version: 'B-R1-advisory-1.0'
  expected_session_revision: number
  title: string
  scheduled_date: string
  project_id: number
}

export interface RecommendationApplicationResponse {
  application_id: string
  task_id: number
  batch_id: string
  candidate_key: string
  replayed: boolean
  source_url: string
}

export interface OfflineBatchFilters {
  dataset_kind: OfflineDatasetKind
  page: number
  page_size: number
  period_start?: string
  period_end?: string
}
