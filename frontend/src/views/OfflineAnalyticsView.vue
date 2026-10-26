<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'

import EChartPanel from '@/components/EChartPanel.vue'
import { buildOfflineChartData, buildProcessInsights, formatBatchInstant, formatRatio, useOfflineAnalytics } from '@/composables/useOfflineAnalytics'
import type { OfflineBatchInfo, OfflineDatasetKind } from '@/types/offlineAnalytics'
import '@/styles/offline-analytics.css'

const route = useRoute()
const router = useRouter()
const requestedBatch = typeof route.query.batch_id === 'string' && /^[\da-f-]{36}$/i.test(route.query.batch_id) ? route.query.batch_id : undefined
const { kind, batches, total, page, totalPages, selectedBatchId, pendingBatchId, detail,
  listLoading, detailLoading, emptyReason, error, staleMessage, forbiddenMessage,
  refreshList, selectBatch, applyPeriod, changeKind, changePage, retry } = useOfflineAnalytics({
  initialKind: route.query.dataset_kind === 'controlled' ? 'controlled' : 'business',
  initialBatchId: requestedBatch,
})
const startInput = ref('')
const endInput = ref('')
const focusedDay = ref('')
const trendMode = ref<'minutes' | 'records'>('minutes')
const charts = computed(() => detail.value ? buildOfflineChartData(detail.value) : null)
const insights = computed(() => detail.value ? buildProcessInsights(detail.value) : [])
const isFixture = computed(() => detail.value?.quality.transaction_fixture === true || detail.value?.quality.permission_fixture === true)
const isEmptyBatch = computed(() => detail.value !== null && detail.value.daily.length === 0)
const visibleDaily = computed(() => detail.value?.daily.filter(day => !focusedDay.value || day.metric_date === focusedDay.value) ?? [])
const selectionValue = computed(() => pendingBatchId.value ?? selectedBatchId.value ?? '')
const historyOutsideList = computed(() => detail.value && !batches.value.some(batch => batch.batch_id === detail.value?.batch_id) ? detail.value : null)
const summary = computed(() => {
  if (!detail.value) return '把任务、记录与提交反馈放在一起，找到这段实践下一步值得跟进的事。'
  const c = detail.value.topic_summary
  return c.cohort_count === 0 ? '本批没有首次提交群组，先结合个人任务和记录了解当前覆盖。'
    : c.cohort_count + '个首次提交群组中，' + c.confirmed_count + '个已获教师确认，' + c.pending_latest_count + '个最新版本仍待评。'
})
const nextStep = computed(() => {
  if (!detail.value) return ''
  if (detail.value.topic_summary.pending_latest_count > 0) return '先核对待评版本与反馈，再安排下一步。'
  if (detail.value.tasks_summary.overdue_unfinished > 0) return '先核对逾期未完任务的计划与当前状态。'
  if (detail.value.records_summary.missing_duration_count > 0) return '记录时长尚有缺失，避免将已知分钟当成全部投入。'
  return '按具体任务要求继续实践。'
})
const emptyCopy = computed(() => ({
  no_completed_batch: '还没有可查看的分析。已有记录在完成离线分析并发布后，会出现在这里。',
  no_matching_batch: '这个周期没有匹配的完整分析，请调整日期或清除筛选。',
  page_empty: '这一页没有批次，请返回前一页。',
}[emptyReason.value ?? 'no_completed_batch']))
const facts = computed(() => {
  if (!detail.value) return []
  const r = detail.value.records_summary, t = detail.value.tasks_summary, c = detail.value.topic_summary
  return [
    { key: 'known-minutes', title: '记录覆盖', value: String(r.known_minutes), unit: '分钟', summary: r.valid_unique_rows + '条记录 · 活跃' + r.active_days + '日',
      note: '时长已知' + r.known_duration_count + '条，缺失' + r.missing_duration_count + '条，明确为零' + r.known_zero_count + '条' },
    { key: 'task-rate', title: '个人任务', value: formatRatio(t.completion_rate), unit: '', summary: t.completed + ' / ' + t.total + '已完成 · 取消' + t.cancelled,
      note: '取消仍在分母 · 逾期未完' + t.overdue_unfinished + '；无任务时不判定全部完成' },
    { key: 'confirmation-count', title: '提交与反馈', value: c.confirmed_count + ' / ' + c.cohort_count, unit: '已确认', summary: '修订' + c.revised_count + ' · 最新待评' + c.pending_latest_count,
      note: '首次确认' + c.first_pass_confirmed_count + '，修订后确认' + c.revised_confirmed_count },
  ]
})

function batchLabel(batch: OfflineBatchInfo): string {
  return batch.period_start + ' 至 ' + batch.period_end + ' · ' + batch.batch_id.slice(0, 8)
}
function chooseKind(event: Event): void { void changeKind((event.target as HTMLSelectElement).value as OfflineDatasetKind) }
function chooseBatch(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  if (value) void selectBatch(value)
}
function clearPeriod(): void {
  startInput.value = ''
  endInput.value = ''
  void applyPeriod('', '')
}
watch(() => detail.value?.batch_id, () => {
  focusedDay.value = ''
  if (detail.value) void router.replace({ query: { ...route.query, dataset_kind: detail.value.dataset_kind, batch_id: detail.value.batch_id } })
})

const colors = ['#155b42', '#548a72', '#8b6838', '#7b8580']
const axis = { axisLabel: { color: '#5c7067' }, axisLine: { lineStyle: { color: '#cfdfd5' } } }
const trendOption = computed<EChartsCoreOption>(() => ({
  color: colors, animationDuration: 320, aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'axis' }, legend: { bottom: 0, textStyle: { color: '#5c7067' } },
  grid: { top: 30, left: 12, right: 20, bottom: 46, containLabel: true },
  xAxis: { ...axis, type: 'category', data: charts.value?.dates.map(day => day.slice(5)) ?? [], boundaryGap: trendMode.value === 'records' },
  yAxis: { ...axis, type: 'value', min: 0, minInterval: 1, name: trendMode.value === 'minutes' ? '分钟' : '条', nameTextStyle: { color: '#5c7067' }, splitLine: { lineStyle: { color: '#e1eae3' } } },
  series: trendMode.value === 'minutes' ? [{ name: '已知分钟', type: 'line', symbolSize: 8, connectNulls: false, data: charts.value?.minutes ?? [] }] : [
    { name: '已知时长记录', type: 'bar', stack: 'records', barMaxWidth: 34, data: charts.value?.records.map((count, index) => count - (charts.value?.missing[index] ?? 0)) ?? [] },
    { name: '时长缺失记录', type: 'bar', stack: 'records', barMaxWidth: 34, data: charts.value?.missing ?? [] },
  ],
}))
function countOption(items: { name: string; value: number }[]): EChartsCoreOption {
  return {
    animationDuration: 320, aria: { enabled: true, decal: { show: true } }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 12, left: 12, right: 32, bottom: 8, containLabel: true },
    xAxis: { ...axis, type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#e1eae3' } } },
    yAxis: { ...axis, type: 'category', inverse: true, data: items.map(item => item.name), axisTick: { show: false } },
    series: [{ type: 'bar', barMaxWidth: 24, label: { show: true, position: 'right', color: '#153c2d' }, data: items.map((item, index) => ({ value: item.value, itemStyle: { color: colors[index % colors.length] } })) }],
  }
}
const figures = computed(() => {
  if (!detail.value) return []
  const r = detail.value.records_summary, t = detail.value.tasks_summary, c = detail.value.topic_summary
  return [
    { key: 'trend', title: trendMode.value === 'minutes' ? '记录分钟的变化' : '有记录的日子', subtitle: '分钟是背景，记录覆盖决定这条趋势能说明多少。', option: trendOption.value, empty: r.valid_unique_rows === 0,
      emptyText: '本批没有学习记录，不能据此判断没有实践。', aria: '记录分钟与记录覆盖趋势图', note: '明确为零保留零点；有记录但全部时长未知时，分钟曲线断开。数值可在下方日明细核对。' },
    { key: 'source', title: '记录从哪里来', subtitle: '可信教学来源由真实教师确认与记录关联证明。', option: countOption(charts.value?.sources ?? []), empty: r.valid_unique_rows === 0,
      emptyText: '本批没有可分类的记录。', aria: '普通记录与可信教学来源分布', note: '普通' + r.ordinary_count + ' · 可信教学' + r.trusted_teaching_count + ' · 未核实声明' + r.unverified_claim_count + '。教师确认不会补造时长。' },
    { key: 'task', title: '任务还剩哪些状态', subtitle: t.completed + ' / ' + t.total + '完成；取消保留在全部任务分母内。', option: countOption(charts.value?.tasks ?? []), empty: t.total === 0,
      emptyText: '本批无个人任务，完成率无样本。', aria: '个人任务完成取消与未完成分布', note: '这是快照时的任务状态，按计划 DATE 归日，不是各历史日的收盘状态。' },
    { key: 'topic', title: '提交的确认路径', subtitle: '以周期内首次提交为群组，追踪截至快照的最新状态。', option: countOption(charts.value?.confirmations ?? []), empty: c.cohort_count === 0,
      emptyText: '本批没有首次提交群组，相关比例无样本。', aria: '首次确认修订后确认与待评提交分布', note: '首次正确可直接确认，修订不是必经步骤。教师确认不等同于平台执行代码测试通过。' },
  ]
})
const ruleTitles: Record<string, string> = {
  revision_observed: '修订与确认，走到了哪一步', first_pass_counterexample: '确认可以有不同路径',
  pending_review: '仍待评阅的最新版本', unknown_duration: '已知分钟覆盖了多少记录', no_tasks: '个人任务当前兑现情况',
}
</script>

<template>
  <div class="page-shell offline-page">
    <nav class="offline-tabs" aria-label="数据页面"><RouterLink to="/analytics">学习与社区数据</RouterLink><RouterLink to="/offline-analytics" aria-current="page">我的学习洞察</RouterLink></nav>
    <header class="offline-heading">
      <h1>我的学习洞察</h1><p>{{ summary }}</p>
      <a v-if="detail && !isEmptyBatch" class="offline-next-step" href="#process-insights">{{ nextStep }} 查看依据</a>
    </header>
    <form class="offline-controls" aria-label="筛选已发布分析" @submit.prevent="applyPeriod(startInput, endInput)">
      <div class="offline-controls__selection">
        <label>数据来源<select aria-label="数据来源" :value="kind" @change="chooseKind"><option value="business">我的业务记录</option><option value="controlled">受控演示样例</option></select></label>
        <label class="offline-batch-field">分析批次<select aria-label="分析批次" :value="selectionValue" :disabled="batches.length === 0 && !historyOutsideList" @change="chooseBatch">
          <option v-if="!selectionValue" value="">{{ listLoading ? '正在读取批次…' : '请选择分析批次' }}</option>
          <option v-if="historyOutsideList" :value="historyOutsideList.batch_id">{{ batchLabel(historyOutsideList) }} · 当前历史</option>
          <option v-for="batch in batches" :key="batch.batch_id" :value="batch.batch_id">{{ batchLabel(batch) }}</option>
        </select></label>
        <button class="secondary-command" type="button" :disabled="listLoading" @click="refreshList()">{{ listLoading ? '刷新中…' : '刷新批次' }}</button>
      </div>
      <div class="offline-controls__dates">
        <label>开始日期<input v-model="startInput" type="date" /></label><label>结束日期<input v-model="endInput" type="date" /></label>
        <button class="primary-command" type="submit" :disabled="listLoading">筛选周期</button><button class="button-quiet" type="button" @click="clearPeriod">清除日期</button>
        <p>按完整分析周期筛选，不截取部分日期重算专题。</p>
      </div>
      <div v-if="totalPages > 1" class="offline-pagination"><span>共 {{ total }} 个批次 · 第 {{ page }} / {{ totalPages }} 页</span><button type="button" :disabled="page <= 1 || listLoading" @click="changePage(page - 1)">上一页</button><button type="button" :disabled="page >= totalPages || listLoading" @click="changePage(page + 1)">下一页</button></div>
    </form>
    <p v-if="detailLoading" class="offline-status" role="status">正在读取所选批次；所有图表将在完整结果返回后一起更新。</p>
    <div v-if="error" class="offline-alert" role="alert"><div><strong>{{ forbiddenMessage || error }}</strong><p v-if="staleMessage">{{ staleMessage }}</p></div><button type="button" @click="retry">重试请求</button></div>
    <section v-if="!detail && !detailLoading && !listLoading && !error" class="offline-empty" aria-label="暂无本人分析">
      <h2>{{ emptyReason === 'no_matching_batch' ? '这个周期还没有分析' : emptyReason === 'page_empty' ? '这一页没有分析' : '从一次完整的分析开始' }}</h2><p>{{ emptyCopy }}</p>
      <p v-if="kind === 'business'">记录和任务仍可正常使用；浏览此页不会启动新的计算或调用 AI。</p><RouterLink to="/workspace/records">查看我的学习记录</RouterLink>
    </section>
    <template v-if="detail">
      <section class="offline-batch-context" aria-label="当前同屏分析批次" :data-batch-id="detail.batch_id">
        <div><strong>{{ detail.period_start }} 至 {{ detail.period_end }}</strong><span class="offline-kind">{{ isFixture ? '验证样例' : detail.dataset_kind === 'controlled' ? '受控演示样例' : '本人业务记录' }}</span></div>
        <p>数据截至 {{ formatBatchInstant(detail.source_cutoff, detail.business_timezone) }}（{{ detail.business_timezone }}） · 批次 {{ detail.batch_id.slice(0, 8) }}</p>
        <p v-if="isFixture">此批用于权限或事务验证，不作为实际 Spark 来源的正式演示。</p><p v-else-if="detail.dataset_kind === 'controlled'">这是虚构业务样例，用于核对学习过程分析，不代表真实长期使用或教学成效。</p>
      </section>
      <p v-if="detail.topic_summary.cohort_count > 0 && detail.topic_summary.cohort_count < 5" class="offline-sample-note">当前只有 {{ detail.topic_summary.cohort_count }} 个首次提交群组，适合逐项跟进，不宜推广为能力或效果结论。</p>
      <dl class="offline-facts" aria-label="三类学习过程事实"><div v-for="fact in facts" :key="fact.key"><dt>{{ fact.title }}</dt><dd><strong :data-testid="fact.key">{{ fact.value }}</strong> {{ fact.unit }}</dd><p>{{ fact.summary }}</p><p>{{ fact.note }}</p></div></dl>
      <div v-if="isEmptyBatch" class="offline-empty offline-empty--batch"><h2>本批没有可绘制样本</h2><p>该批次已完成且属于本人；无记录、任务或提交时显示无样本，不把空集合解释为全部完成。</p></div>
      <div v-else class="offline-chart-grid" :data-chart-batch="detail.batch_id">
        <section v-for="figure in figures" :key="figure.key" class="offline-figure">
          <div class="offline-figure__heading"><div><h2>{{ figure.title }}</h2><p>{{ figure.subtitle }}</p></div><div v-if="figure.key === 'trend'" class="offline-view-switch" role="group" aria-label="趋势视图"><button type="button" :aria-pressed="trendMode === 'minutes'" @click="trendMode = 'minutes'">分钟</button><button type="button" :aria-pressed="trendMode === 'records'" @click="trendMode = 'records'">记录数</button></div></div>
          <EChartPanel :option="figure.option" :empty="figure.empty" :empty-text="figure.emptyText" :ariaLabel="figure.aria" /><p class="offline-chart-note">{{ figure.note }}</p>
        </section>
      </div>
      <section id="process-insights" class="offline-insights" aria-labelledby="process-insights-title">
        <div class="offline-section-heading"><h2 id="process-insights-title">从事实到下一步</h2><p>每条提示使用本批数据和固定规则，不需要运行 AI 工作流。</p></div>
        <article v-for="insight in insights" :key="insight.id" class="offline-insight" :data-rule="insight.id">
          <div class="offline-insight__title"><h3>{{ ruleTitles[insight.id] || insight.title }}</h3><span>{{ insight.denominator === 0 ? '无样本' : insight.triggered ? '已观察到' : '未触发' }}</span></div>
          <p class="offline-insight__evidence">{{ insight.evidence }}</p><p>{{ insight.action }}</p>
          <details><summary>查看规则与适用范围</summary><dl><div><dt>判断条件</dt><dd><code>{{ insight.condition }}</code></dd></div><div><dt>样本与分母</dt><dd>{{ insight.numerator }} / {{ insight.denominator }}</dd></div><div><dt>涉及日期</dt><dd>{{ insight.dates.join('、') || '本批没有对应日期样本' }}</dd></div></dl><p>{{ insight.boundary }}</p></details>
        </article>
      </section>
      <section class="offline-daily" aria-labelledby="offline-daily-title">
        <div class="offline-section-heading"><div><h2 id="offline-daily-title">按日核对事实</h2><p>日明细用于定位来源；上方图表与专题始终覆盖同一完整批次。</p></div><label>定位日期<input v-model="focusedDay" type="date" :min="detail.period_start" :max="detail.period_end" /></label><button v-if="focusedDay" class="button-quiet" type="button" @click="focusedDay = ''">查看全部日期</button></div>
        <div class="offline-table-scroll" tabindex="0" aria-label="学习过程日明细，可横向滚动">
          <table><caption>{{ detail.period_start }} 至 {{ detail.period_end }} · {{ detail.business_timezone }} · 批次 {{ detail.batch_id.slice(0, 8) }}</caption><thead><tr><th scope="col">日期</th><th scope="col">记录 / 缺失</th><th scope="col">已知分钟</th><th scope="col">可信教学</th><th scope="col">完成 / 任务</th><th scope="col">取消</th><th scope="col">群组 / 修订 / 确认</th></tr></thead>
            <tbody><tr v-for="day in visibleDaily" :key="day.metric_date"><th scope="row">{{ day.metric_date }}</th><td>{{ day.records }} / {{ day.missing_duration_count }}</td><td>{{ day.known_duration_count > 0 ? day.known_minutes : day.records > 0 ? '时长未知' : '无记录' }}</td><td>{{ day.trusted_teaching_count }}</td><td>{{ day.completed }} / {{ day.task_total }}</td><td>{{ day.cancelled }}</td><td>{{ day.cohort_count }} / {{ day.revised_count }} / {{ day.confirmed_count }}</td></tr></tbody></table>
          <p v-if="visibleDaily.length === 0" class="offline-no-daily">{{ focusedDay ? '所定位日期没有日汇总行；没有把缺失行补成真实活动。完整批次的统计保持不变。' : '本批没有日汇总行。' }}</p>
        </div>
      </section>
      <details class="offline-provenance"><summary>分析口径与来源</summary>
        <dl><div><dt>完整批次</dt><dd>{{ detail.batch_id }}</dd></div><div><dt>发布完成</dt><dd>{{ formatBatchInstant(detail.published_at, detail.business_timezone) }}</dd></div><div><dt>数据快照</dt><dd>{{ detail.source.snapshot_id }}</dd></div><div><dt>计算任务</dt><dd>{{ detail.source.job_id }}</dd></div><div><dt>指标 / 规则</dt><dd>{{ detail.metric_version }} / {{ detail.rule_version }}</dd></div><div><dt>来源结构</dt><dd>{{ detail.schema_version }}</dd></div><div><dt>质量对账</dt><dd>{{ detail.quality.reconciled === true && detail.quality.fatal_errors === 0 ? '通过' : '需核对' }}</dd></div><div><dt>独立答案对照</dt><dd>{{ detail.quality.independent_answers_matched === true ? '本批指标已与独立核算答案逐项对照' : '此批未附带独立核对标记；不据此宣称完成评价' }}</dd></div></dl>
        <p>快照表示已保存的事实，不重建未记录的历史状态。记录量、修订与教师确认均不能直接证明能力提升或 AI 教学效果。</p>
      </details>
    </template>
  </div>
</template>
