import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'

import { getApiErrorMessage, getApiErrorStatus } from '@/api/errors'
import {
  getOfflineBatch,
  listOfflineBatches,
  OfflineAnalyticsCompatibilityError,
} from '@/api/offlineAnalytics'
import { useAuthStore } from '@/stores/auth'
import type {
  OfflineBatchDetail,
  OfflineBatchFilters,
  OfflineBatchInfo,
  OfflineDatasetKind,
  OfflineEmptyReason,
  OfflineRatio,
  OfflineTopicSummary,
} from '@/types/offlineAnalytics'

interface RefreshOptions {
  resetPage?: boolean
  revalidateSelected?: boolean
}

export interface OfflineAnalyticsOptions {
  initialKind?: OfflineDatasetKind
  initialBatchId?: string
}

export function useOfflineAnalytics(options: OfflineAnalyticsOptions = {}) {
  const auth = useAuthStore()
  const kind = ref<OfflineDatasetKind>('business')
  const periodStart = ref('')
  const periodEnd = ref('')
  const page = ref(1)
  const pageSize = ref(20)
  const batches = shallowRef<OfflineBatchInfo[]>([])
  const total = ref(0)
  const emptyReason = ref<OfflineEmptyReason | null>(null)
  const selectedBatchId = ref<string | null>(null)
  const pendingBatchId = ref<string | null>(null)
  const detail = shallowRef<OfflineBatchDetail | null>(null)
  const listLoading = ref(false)
  const detailLoading = ref(false)
  const error = ref<string | null>(null)
  const staleMessage = ref<string | null>(null)
  const forbiddenMessage = ref<string | null>(null)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  let listController: AbortController | undefined
  let detailController: AbortController | undefined
  let listSequence = 0
  let detailSequence = 0
  let sessionGeneration = 0
  let disposed = false
  let initialSessionPending = true
  let retryTarget: { type: 'list'; chooseFirst?: boolean } | { type: 'detail'; id: string } = { type: 'list' }

  function hasSession(): boolean {
    return auth.token !== null && auth.currentUser !== null
  }

  function cancel(): void {
    ++listSequence
    ++detailSequence
    listController?.abort()
    detailController?.abort()
    listLoading.value = false
    detailLoading.value = false
    pendingBatchId.value = null
  }

  function clearSelection(): void {
    detail.value = null
    selectedBatchId.value = null
    pendingBatchId.value = null
    staleMessage.value = null
  }

  function clearPrivateData(): void {
    cancel()
    clearSelection()
    batches.value = []
    total.value = 0
    emptyReason.value = null
    error.value = null
    forbiddenMessage.value = null
  }

  function handleFailure(cause: unknown, fallback: string): void {
    const status = getApiErrorStatus(cause)
    error.value = cause instanceof OfflineAnalyticsCompatibilityError
      ? cause.message
      : getApiErrorMessage(cause, fallback)
    if (status === 401 || status === 403 || status === 404) {
      cancel()
      clearSelection()
      batches.value = []
      total.value = 0
      emptyReason.value = null
      forbiddenMessage.value = status === 401
        ? '登录已失效，请重新登录后查看本人分析'
        : '该批次不可访问，请刷新本人批次列表'
    } else if (detail.value) {
      staleMessage.value = `请求未完成，仍显示上一成功批次；源截止 ${formatBatchInstant(detail.value.source_cutoff, detail.value.business_timezone)}`
    }
  }

  async function selectBatch(batchId: string): Promise<void> {
    if (!hasSession() || disposed) return
    detailController?.abort()
    detailController = new AbortController()
    const requestSequence = ++detailSequence
    const generation = sessionGeneration
    detailLoading.value = true
    pendingBatchId.value = batchId
    error.value = null
    forbiddenMessage.value = null
    retryTarget = { type: 'detail', id: batchId }
    try {
      const result = await getOfflineBatch(batchId, detailController.signal)
      if (disposed || requestSequence !== detailSequence || generation !== sessionGeneration) return
      // 标题、图表和专题只在完整详情成功后一起更换。
      detail.value = result
      selectedBatchId.value = result.batch_id
      staleMessage.value = null
    } catch (cause: unknown) {
      if (!disposed && requestSequence === detailSequence && generation === sessionGeneration) {
        handleFailure(cause, '批次读取失败，请重试')
      }
    } finally {
      if (!disposed && requestSequence === detailSequence && generation === sessionGeneration) {
        detailLoading.value = false
        pendingBatchId.value = null
      }
    }
  }

  async function loadList(options: RefreshOptions = {}, chooseFirst = false): Promise<void> {
    if (!hasSession() || disposed) return
    if (options.resetPage) page.value = 1
    listController?.abort()
    listController = new AbortController()
    const requestSequence = ++listSequence
    const selectionSequence = detailSequence
    const generation = sessionGeneration
    const filters: OfflineBatchFilters = {
      dataset_kind: kind.value,
      page: page.value,
      page_size: pageSize.value,
      ...(periodStart.value && periodEnd.value
        ? { period_start: periodStart.value, period_end: periodEnd.value }
        : {}),
    }
    listLoading.value = true
    error.value = null
    forbiddenMessage.value = null
    retryTarget = { type: 'list', chooseFirst }
    try {
      const result = await listOfflineBatches(filters, listController.signal)
      if (disposed || requestSequence !== listSequence || generation !== sessionGeneration) return
      batches.value = result.items
      total.value = result.total
      page.value = result.page
      emptyReason.value = result.empty_reason
      // 列表返回期间若用户另选了批次，不能用列表默认项覆盖该选择。
      if (selectionSequence !== detailSequence) return
      if (chooseFirst && result.items.length === 0) {
        ++detailSequence
        detailController?.abort()
        detailLoading.value = false
        clearSelection()
      } else if ((chooseFirst || !detail.value) && result.items[0]) {
        await selectBatch(result.items[0].batch_id)
      } else if (detail.value && options.revalidateSelected !== false) {
        // 新发布结果只进入列表，刷新仍复核当前历史批次。
        await selectBatch(detail.value.batch_id)
      }
    } catch (cause: unknown) {
      if (!disposed && requestSequence === listSequence && generation === sessionGeneration) {
        handleFailure(cause, '分析批次列表读取失败，请重试')
      }
    } finally {
      if (!disposed && requestSequence === listSequence && generation === sessionGeneration) listLoading.value = false
    }
  }

  function refreshList(options: RefreshOptions = {}): Promise<void> {
    return loadList(options)
  }

  async function applyPeriod(start: string, end: string): Promise<void> {
    if ((start === '') !== (end === '')) {
      error.value = '请同时选择开始日期和结束日期'
      return
    }
    const span = (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000
    if (start && (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)
      || !Number.isFinite(span) || span < 0 || span >= 90
      || new Date(`${start}T00:00:00Z`).toISOString().slice(0, 10) !== start
      || new Date(`${end}T00:00:00Z`).toISOString().slice(0, 10) !== end)) {
      error.value = '查询日期范围需为1至90天'
      return
    }
    cancel()
    periodStart.value = start
    periodEnd.value = end
    await loadList({ resetPage: true }, true)
  }

  async function changeKind(nextKind: OfflineDatasetKind): Promise<void> {
    cancel()
    kind.value = nextKind
    await loadList({ resetPage: true }, true)
  }

  async function changePage(nextPage: number): Promise<void> {
    if (!Number.isInteger(nextPage) || nextPage < 1) return
    page.value = nextPage
    await loadList({ revalidateSelected: false })
  }

  async function retry(): Promise<void> {
    if (retryTarget.type === 'detail') await selectBatch(retryTarget.id)
    else await loadList({}, retryTarget.chooseFirst ?? false)
  }

  watch(() => [auth.token, auth.currentUser?.id] as const, () => {
    ++sessionGeneration
    clearPrivateData()
    page.value = 1
    periodStart.value = ''
    periodEnd.value = ''
    kind.value = initialSessionPending ? (options.initialKind ?? 'business') : 'business'
    if (hasSession()) {
      const initialBatchId = initialSessionPending ? options.initialBatchId : undefined
      initialSessionPending = false
      if (initialBatchId && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(initialBatchId)) {
        error.value = '批次编号格式无效，请从本人批次列表重新选择'
        return
      }
      void refreshList({ revalidateSelected: false })
      // 先建立列表请求，再显式选择，使列表完成时不能用默认项覆盖URL中的固定批次。
      if (initialBatchId) void selectBatch(initialBatchId)
    }
  }, { immediate: true, flush: 'sync' })

  onScopeDispose(() => {
    disposed = true
    ++sessionGeneration
    clearPrivateData()
  })

  return {
    kind, periodStart, periodEnd, page, pageSize, batches, total, totalPages, emptyReason,
    selectedBatchId, pendingBatchId, detail, listLoading, detailLoading, error,
    staleMessage, forbiddenMessage, refreshList, selectBatch, applyPeriod, changeKind,
    changePage, retry, cancel,
  }
}

export function formatBatchInstant(instant: string, timezone = 'Asia/Shanghai'): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(new Date(instant))
}

export function formatRatio(ratio: OfflineRatio): string {
  return ratio.denominator === 0 || ratio.percent === null
    ? '无样本'
    : `${Number(ratio.percent).toFixed(1)}%`
}

export interface OfflineChartSlice {
  name: string
  value: number
}

export interface OfflineChartData {
  dates: string[]
  minutes: Array<number | null>
  records: number[]
  missing: number[]
  zeros: number[]
  active: number[]
  sources: OfflineChartSlice[]
  tasks: OfflineChartSlice[]
  taskCompleted: number[]
  taskCancelled: number[]
  taskOther: number[]
  taskOverdue: number[]
  cohortCount: number[]
  revisedCount: number[]
  confirmedCount: number[]
  confirmations: OfflineChartSlice[]
  reviewHistogram: OfflineChartSlice[]
}

export function teachingSummary(batch: OfflineBatchDetail): OfflineTopicSummary {
  return batch.schema_version === 'scholarhub-source-2.0' ? batch.topic_summary.teaching : batch.topic_summary
}

export function buildOfflineChartData(batch: OfflineBatchDetail): OfflineChartData {
  const r = batch.records_summary
  const t = batch.tasks_summary
  const c = teachingSummary(batch)
  return {
    dates: batch.daily.map(day => day.metric_date),
    minutes: batch.daily.map(day => day.known_duration_count > 0 ? day.known_minutes : day.records > 0 ? null : 0),
    records: batch.daily.map(day => day.records),
    missing: batch.daily.map(day => day.missing_duration_count),
    zeros: batch.daily.map(day => day.known_zero_count),
    active: batch.daily.map(day => day.records > 0 ? 1 : 0),
    sources: [
      { name: '普通记录', value: r.ordinary_count },
      { name: '可信教学来源', value: r.trusted_teaching_count },
      { name: '未核实来源声明', value: r.unverified_claim_count },
    ],
    tasks: [
      { name: '已完成', value: t.completed },
      { name: '已取消', value: t.cancelled },
      { name: '逾期未完', value: t.overdue_unfinished },
      { name: '其他未完', value: t.total - t.completed - t.cancelled - t.overdue_unfinished },
    ],
    taskCompleted: batch.daily.map(day => day.completed),
    taskCancelled: batch.daily.map(day => day.cancelled),
    taskOther: batch.daily.map(day => day.task_total - day.completed - day.cancelled),
    taskOverdue: batch.daily.map(day => day.overdue_unfinished),
    cohortCount: batch.daily.map(day => day.cohort_count),
    revisedCount: batch.daily.map(day => day.revised_count),
    confirmedCount: batch.daily.map(day => day.confirmed_count),
    confirmations: [
      { name: '首次即确认', value: c.first_pass_confirmed_count },
      { name: '修订后确认', value: c.revised_confirmed_count },
      { name: '最新待评', value: c.pending_latest_count },
      { name: '其他未确认', value: c.cohort_count - c.confirmed_count - c.pending_latest_count },
    ],
    reviewHistogram: ['[0,60)', '[60,240)', '[240,1440)', '[1440,+inf)'].map(name => ({
      name, value: c.first_review_histogram[name] ?? 0,
    })),
  }
}

export interface ProcessInsight {
  id: string
  title: string
  condition: string
  triggered: boolean
  numerator: number
  denominator: number
  dates: string[]
  evidence: string
  boundary: string
  action: string
}

export function buildProcessInsights(batch: OfflineBatchDetail): ProcessInsight[] {
  const r = batch.records_summary
  const t = batch.tasks_summary
  const c = teachingSummary(batch)
  const cohortDates = batch.daily.filter(day => day.cohort_count > 0).map(day => day.metric_date)
  return [
    {
      id: 'revision_observed', title: '提交修订进展', condition: 'revised_count > 0',
      triggered: c.revised_count > 0, numerator: c.revised_count, denominator: c.cohort_count,
      dates: batch.daily.filter(day => day.revised_count > 0).map(day => day.metric_date),
      evidence: c.cohort_count === 0 ? '本周期没有首次提交群组，修订比例无样本。'
        : `${c.cohort_count}个首次提交群组中，${c.revised_count}个有修订；其中${c.revised_confirmed_count}个修订后获教师确认。`,
      boundary: `按V1业务日归组，截至同一快照；修订后确认样本为${c.revised_confirmed_count}/${c.revised_count}，不能据此判断修订带来能力提升。`,
      action: c.pending_latest_count > 0 ? '查看待评提交的反馈与当前版本，确认是否需要补充材料。' : '保留已确认版本与反馈，继续按具体任务要求记录实践。',
    },
    {
      id: 'first_pass_counterexample', title: '首次确认的反例', condition: 'first_pass_confirmed_count > 0',
      triggered: c.first_pass_confirmed_count > 0, numerator: c.first_pass_confirmed_count, denominator: c.cohort_count,
      // 当前API没有逐日首次确认拆分，不能把确认日期推算为首提交日期。
      dates: cohortDates,
      evidence: c.cohort_count === 0 ? '无首次提交群组，不能判断是否存在首次确认。'
        : c.first_pass_confirmed_count > 0 ? `有${c.first_pass_confirmed_count}个群组首次即获确认，修订不是确认的必经步骤。`
          : '本批未观察到首次即确认；未触发不代表所有任务都必须修订。',
      boundary: '日期为群组首提交日覆盖；教师确认不等于平台执行代码测试，也不能代表全部被布置的任务。',
      action: '结合首次确认与修订后确认并列查看，避免将修订画成必经漏斗。',
    },
    {
      id: 'pending_review', title: '最新版本待评', condition: 'pending_latest_count > 0',
      triggered: c.pending_latest_count > 0, numerator: c.pending_latest_count, denominator: c.cohort_count,
      dates: cohortDates,
      evidence: `${c.pending_latest_count}/${c.cohort_count}个群组的最新版本仍待评；首次反馈覆盖${c.first_review_covered}/${c.cohort_count}，已反馈样本平均等待${c.first_review_wait_mean_minutes === null ? '无样本' : `${c.first_review_wait_mean_minutes}分钟`}。`
        + `等待分布：少于60分钟${c.first_review_histogram['[0,60)'] ?? 0}个，60至不足240分钟${c.first_review_histogram['[60,240)'] ?? 0}个，240至不足1440分钟${c.first_review_histogram['[240,1440)'] ?? 0}个，1440分钟及以上${c.first_review_histogram['[1440,+inf)'] ?? 0}个。`,
      boundary: batch.dataset_kind === 'controlled' ? '这是受控业务样例；自动化API操作间隔不能解释为自然教师响应时长。'
        : '等待依据已保存的首次反馈计算；没有反馈不能填为零，也不是学习投入时长。',
      action: c.pending_latest_count > 0 ? '等待或核对教师反馈；下一次发布后再比较新的完整批次。' : '本批没有待评项，后续提交仍需按实际反馈核对。',
    },
    {
      id: 'unknown_duration', title: '记录时长覆盖', condition: 'missing_duration_count > 0',
      triggered: r.missing_duration_count > 0, numerator: r.missing_duration_count, denominator: r.valid_unique_rows,
      dates: batch.daily.filter(day => day.missing_duration_count > 0).map(day => day.metric_date),
      evidence: `${r.valid_unique_rows}条记录中，${r.known_duration_count}条已知时长合计${r.known_minutes}分钟；${r.missing_duration_count}条未知，${r.known_zero_count}条明确为零。`,
      boundary: '已知分钟仅代表有时长字段的记录覆盖；NULL与零分开，不能用日志量推断投入或掌握程度。',
      action: r.missing_duration_count > 0 ? '后续有可靠时长时再记录；不要为缺失记录估算或填零。' : '继续保留时长与发生日期，结合任务及反馈理解过程。',
    },
    {
      id: 'no_tasks', title: '个人任务兑现', condition: 'task_total = 0',
      triggered: t.total === 0, numerator: t.completed, denominator: t.total,
      dates: batch.daily.filter(day => day.task_total > 0).map(day => day.metric_date),
      evidence: t.total === 0 ? '本批没有个人任务，完成率无样本。'
        : `已完成${t.completed}/${t.total}（${formatRatio(t.completion_rate)}）；取消${t.cancelled}仍在分母，逾期未完${t.overdue_unfinished}。`,
      boundary: '这是截至快照的当前任务状态；计划日期是DATE原值，不能重建未保存的历史收盘状态，也不等于教学确认。',
      action: t.overdue_unfinished > 0 ? '先核对逾期未完任务的计划与当前状态，再安排下一步。' : '根据实际任务安排继续维护计划，不从无样本推断全部完成。',
    },
  ]
}
