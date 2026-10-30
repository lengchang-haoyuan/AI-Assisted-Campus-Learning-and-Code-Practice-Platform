<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import type { EChartsCoreOption } from 'echarts/core'
import EChartPanel from '@/components/EChartPanel.vue'
import { getApiErrorMessage } from '@/api/errors'
import { applyOfflineRecommendation } from '@/api/offlineAnalytics'
import { getProject, listProjects } from '@/api/projects'
import { formatBatchInstant } from '@/composables/useOfflineAnalytics'
import { PRACTICE_STATUS } from '@/domain/practice'
import { getLocalDateValue } from '@/domain/workspace'
import { useAuthStore } from '@/stores/auth'
import type { ProjectResponse } from '@/types/project'
import type { OfflineBatchDetailV2, OfflineRecommendation, RecommendationApplicationInput, RecommendationApplicationResponse } from '@/types/offlineAnalytics'

const props = defineProps<{ batch: OfflineBatchDetailV2 }>()
const auth = useAuthStore()
const practice = computed(() => props.batch.topic_summary.practice)
const selected = shallowRef<OfflineRecommendation | null>(null)
const projects = shallowRef<ProjectResponse[]>([])
const title = ref(''), scheduledDate = ref(''), projectId = ref(0), reviewed = ref(false)
const loading = ref(false), saving = ref(false), error = ref<string | null>(null)
const pending = shallowRef<RecommendationApplicationInput | null>(null)
const applied = ref<Record<string, RecommendationApplicationResponse>>({})
let generation = 0, disposed = false
const measures = computed(() => [
  ['实践会话', practice.value.session_count], ['实际提交', practice.value.submission_event_count],
  ['尚无提交', practice.value.no_submission_count], ['本人审阅结束', practice.value.personal_end_count],
  ['AI 请求', practice.value.request_count], ['取消', practice.value.cancel_count], ['恢复', practice.value.resume_count],
] as const)
const actionChart = computed<EChartsCoreOption>(() => ({
  color: ['#155b42'], animationDuration: 320,
  aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'axis', renderMode: 'richText', axisPointer: { type: 'shadow' } },
  grid: { top: 12, left: 12, right: 40, bottom: 12, containLabel: true },
  xAxis: { type: 'value', name: '次', min: 0, minInterval: 1, axisLabel: { color: '#5c7067' }, splitLine: { lineStyle: { color: '#e1eae3' } } },
  yAxis: { type: 'category', inverse: true, data: ['实际提交', 'AI 请求', '本人审阅结束', '取消', '恢复'],
    axisLabel: { color: '#5c7067' }, axisLine: { lineStyle: { color: '#cfdfd5' } }, axisTick: { show: false } },
  series: [{ name: '本周期动作次数', type: 'bar', barMaxWidth: 24,
    label: { show: true, position: 'right', color: '#153c2d' },
    data: [practice.value.submission_event_count, practice.value.request_count, practice.value.personal_end_count, practice.value.cancel_count, practice.value.resume_count] }],
}))
function clear(): void {
  ++generation; selected.value = null; pending.value = null; projects.value = []
  loading.value = saving.value = reviewed.value = false; error.value = null; applied.value = {}
}
watch(() => [props.batch.batch_id, auth.token, auth.currentUser?.id], clear, { flush: 'sync' })
onScopeDispose(() => { disposed = true; clear() })

async function open(candidate: OfflineRecommendation): Promise<void> {
  if (saving.value || !auth.token || !auth.currentUser) return
  const ticket = ++generation
  selected.value = candidate; pending.value = null; error.value = null; reviewed.value = false
  title.value = candidate.title; scheduledDate.value = getLocalDateValue(); projectId.value = candidate.project_id
  projects.value = []; loading.value = true
  try {
    const page = await listProjects({ page: 1, pageSize: 100 })
    const items = page.items.some(project => project.id === candidate.project_id)
      ? page.items : [await getProject(candidate.project_id), ...page.items]
    if (!disposed && ticket === generation) projects.value = items
  } catch (cause: unknown) {
    if (!disposed && ticket === generation) error.value = getApiErrorMessage(cause, '本人项目读取失败，请重新打开建议重试')
  } finally { if (!disposed && ticket === generation) loading.value = false }
}
function close(): void {
  if (saving.value) return
  ++generation; selected.value = null; pending.value = null; error.value = null; reviewed.value = false; loading.value = false
}
function revise(): void { pending.value = null; reviewed.value = false; error.value = null }
async function apply(): Promise<void> {
  const candidate = selected.value
  if (!candidate || saving.value || loading.value || !reviewed.value || !auth.token || !auth.currentUser) return
  if (!pending.value) {
    if (!title.value.trim() || title.value.trim().length > 160 || !/^\d{4}-\d{2}-\d{2}$/.test(scheduledDate.value)
      || !projects.value.some(project => project.id === projectId.value)) {
      error.value = '请核对任务标题、日期和本人项目。'; return
    }
    pending.value = { request_key: `s10:${crypto.randomUUID()}`, candidate_key: candidate.candidate_key,
      expected_metric_version: 'learning-process-2.0', expected_rule_version: candidate.rule_version,
      expected_session_revision: candidate.session_revision, title: title.value.trim(),
      scheduled_date: scheduledDate.value, project_id: projectId.value }
  }
  const ticket = generation, batchId = props.batch.batch_id, payload = pending.value
  saving.value = true; error.value = null
  try {
    const result = await applyOfflineRecommendation(batchId, payload)
    if (!disposed && ticket === generation) {
      applied.value = { ...applied.value, [candidate.candidate_key]: result }
      selected.value = null; pending.value = null; reviewed.value = false
    }
  } catch (cause: unknown) {
    if (!disposed && ticket === generation) error.value = getApiErrorMessage(cause, '任务创建结果尚未确认，可重试原请求或重新审阅')
  } finally { if (!disposed && ticket === generation) saving.value = false }
}
function declared(value: boolean | null): string { return value === null ? '未知 / 未提供' : value ? '本人声明已自测' : '本人声明未自测' }
const comparison = { matched: '声明值一致', mismatched: '声明值不一致', unknown: '缺少声明值' }
</script>

<template>
  <section class="offline-practice" aria-labelledby="practice-analysis-title" :data-practice-batch="batch.batch_id">
    <div class="offline-section-heading"><div><h2 id="practice-analysis-title">这段实践做了什么</h2><p>会话按创建日进入本周期，状态取同一快照，动作只统计截止前的本周期事件。</p></div></div>
    <dl class="offline-practice-measures"><div v-for="[label, value] in measures" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div></dl>
    <div class="offline-practice-action-chart" :data-practice-action-chart="batch.batch_id">
      <h3>本周期实践动作</h3>
      <EChartPanel :option="actionChart" :empty="practice.session_count === 0" empty-text="本周期没有实践会话样本。" ariaLabel="实际提交、AI请求、本人审阅结束、取消和恢复的次数" />
      <p class="offline-chart-note">各类动作分别计数，同一会话可以产生多类动作，不构成互斥占比或正确率。</p>
    </div>
    <p class="offline-chart-note">本人结束表示已审阅本次材料；提交与请求次数只表示操作过程。</p>
    <p class="offline-chart-note">事件覆盖从 {{ practice.observed_event_coverage_start ? formatBatchInstant(practice.observed_event_coverage_start, batch.business_timezone) : '尚无保留事件' }} 起；这是本人当前最早保留事件，不补造此前历史。教师确认：{{ practice.teacher_confirmation_count === null ? '未知 / 未提供' : practice.teacher_confirmation_count }}。</p>

    <p v-if="practice.sessions.length === 0" class="offline-no-daily">本周期没有实践会话样本。</p>
    <details v-else class="offline-practice-sessions"><summary>逐会话核对提交与来源（{{ practice.session_count }}）</summary>
      <article v-for="session in practice.sessions" :key="session.session_id" class="offline-practice-session" :data-session-id="session.session_id">
        <div class="offline-insight__title"><h3>会话 {{ session.session_id.slice(0, 8) }} · {{ session.current_step_key === 'implement' ? '代码实践' : '理解任务' }}</h3><span>{{ PRACTICE_STATUS[session.status] }}</span></div>
        <p>{{ session.template_id }} / {{ session.template_version }} · 截至快照共{{ session.attempt_count }}份提交 · 资料 v{{ session.context_version }} · 会话 v{{ session.revision }}</p>
        <dl><div><dt>自我声明</dt><dd>{{ declared(session.self_statement) }}</dd></div><div><dt>输出值核对</dt><dd>{{ comparison[session.output_comparison] }}，未执行代码</dd></div><div><dt>AI 建议来源</dt><dd>{{ session.advice.length }} 条模型报告类别引用</dd></div><div><dt>本人审阅</dt><dd>{{ session.personal_reviewed ? '已审阅本次材料' : '尚未记录审阅' }}</dd></div><div><dt>教师确认</dt><dd>{{ session.teacher_confirmation === null ? '未知 / 未提供' : session.teacher_confirmation ? '已有正式来源' : '正式来源未确认' }}</dd></div></dl>
        <RouterLink :to="{ path: `/projects/${session.project_id}/practice`, query: { session: session.session_id } }">查看会话与提交历史</RouterLink>
      </article>
    </details>

    <div class="offline-section-heading offline-practice-recommend-heading"><div><h2>可选的下一步自测</h2><p>同类模型建议在不同提交中重复出现时，提醒补一个边界自测。是否采纳由你决定。</p></div></div>
    <p v-if="batch.recommendations.length === 0" class="offline-no-daily">本批没有满足重复建议提醒条件的候选；缺少引用时不推断问题已经解决。</p>
    <article v-for="candidate in batch.recommendations" :key="candidate.candidate_key" class="offline-insight offline-recommendation" :data-candidate="candidate.candidate_key">
      <h3>{{ candidate.title }}</h3><p class="offline-insight__evidence">{{ candidate.explanation }}</p>
      <p>来源：模型报告 · {{ candidate.criterion_id }} / {{ candidate.issue_type }} · {{ candidate.references.length }} 条已绑定引用。这里只提示重复建议，不认定代码存在错误。</p>
      <details><summary>核对建议原始引用与批次</summary><dl><div><dt>规则 / 指标</dt><dd>{{ candidate.rule_version }} / {{ batch.metric_version }}</dd></div><div><dt>批次 / 截止</dt><dd>{{ batch.batch_id }} / {{ formatBatchInstant(batch.source_cutoff, batch.business_timezone) }}</dd></div><div><dt>会话 / 当前提交</dt><dd>{{ candidate.session_id }} / {{ candidate.attempt_id }}（第 {{ candidate.attempt_no }} 版）</dd></div></dl>
        <ul class="offline-advice-references"><li v-for="reference in candidate.references" :key="reference.issue_event_id">第 {{ reference.attempt_no }} 版 · {{ reference.criterion_id }} / {{ reference.issue_type }}<br />attempt {{ reference.attempt_id }}<br />operation {{ reference.operation_id }} · AI 请求 {{ reference.ai_request_id }}<br />建议事件 {{ reference.review_event_id }} · 类别事件 {{ reference.issue_event_id }} · {{ reference.prompt_version || '历史提示版本未知' }}</li></ul>
        <RouterLink :to="{ path: `/projects/${candidate.project_id}/practice`, query: { session: candidate.session_id } }">回到实践核对建议</RouterLink>
      </details>
      <p v-if="applied[candidate.candidate_key]" class="offline-application-result" role="status">{{ applied[candidate.candidate_key]?.replayed ? '已找到原任务' : '已创建独立任务' }} #{{ applied[candidate.candidate_key]?.task_id }}。<RouterLink :to="{ path: '/learning/tasks', query: { task_id: applied[candidate.candidate_key]?.task_id } }">查看任务及来源</RouterLink></p>
      <form v-else-if="selected?.candidate_key === candidate.candidate_key" class="offline-recommendation-form" aria-label="审阅并采纳建议" @submit.prevent="apply">
        <p v-if="loading" role="status">正在读取本人项目…</p>
        <label>任务标题<input v-model="title" required maxlength="160" :disabled="saving || pending !== null" /></label>
        <div class="offline-recommendation-fields"><label>计划日期<input v-model="scheduledDate" type="date" required :disabled="saving || pending !== null" /></label><label>本人项目<select v-model.number="projectId" aria-label="本人项目" required :disabled="loading || saving || pending !== null"><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label></div>
        <label class="offline-review-check"><input v-model="reviewed" type="checkbox" :disabled="saving || pending !== null" required />我已审阅标题、日期、项目和建议来源，选择创建这项自测任务。</label>
        <p>这会创建一项独立任务，保留建议来源；计划集合保持原样。</p>
        <p v-if="error" class="offline-recommendation-error" role="alert">{{ error }}</p>
        <div class="offline-recommendation-actions"><button class="primary-command" type="submit" :disabled="saving || loading || !reviewed || projects.length === 0">{{ saving ? '正在确认任务…' : pending ? '重试原请求' : '采纳并创建一次任务' }}</button><button v-if="pending" class="button-quiet" type="button" :disabled="saving" @click="revise">重新审阅</button><button class="button-quiet" type="button" :disabled="saving" @click="close">暂不采纳</button></div>
      </form>
      <button v-else class="secondary-command offline-recommendation-open" type="button" :disabled="saving" @click="open(candidate)">审阅并采纳建议</button>
    </article>
  </section>
</template>
