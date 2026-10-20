<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'

import WorkflowNodeResultContent from '@/components/WorkflowNodeResultContent.vue'
import { WORKFLOW_NODE_TEMPLATES } from '@/domain/workflow'
import type { JsonValue, WorkflowRunNodeResponse, WorkflowRunResponse, WorkflowRunMode } from '@/types/workflow'

const props = defineProps<{
  runs: WorkflowRunResponse[]
  selected: WorkflowRunResponse | null
  loading: boolean
  busy: boolean
  error: string | null
  blockers: string[]
  mode: WorkflowRunMode
  page: number
  totalPages: number
}>()
const emit = defineEmits<{
  refresh: [page?: number]
  select: [id: number]
  'update:mode': [mode: WorkflowRunMode]
}>()
const labels: Record<string, string> = {
  pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已中止',
}
const errorHints: Record<string, string> = {
  authentication: '请检查后端 DeepSeek 密钥及启动环境，并重启后端。',
  configuration: '请配置后端 DeepSeek API Key 后重启。',
  rate_limit: '模型服务限流，请稍后重试。',
  agent_output_invalid: 'AI 返回的内容不符合节点要求，可重试未完成节点。',
  workflow_timeout: '本次运行超时，可继续运行未完成节点。',
  budget_exhausted: '本次生成预算已用尽，可分成较小的工作流运行。',
}
type Metric = 'latency_ms' | 'total_tokens'
const metric = ref<Metric>('latency_ms')
// 同类型节点也可能出现多次，按本次请求编号保存选择，避免历史记录互相串位。
const selectedNodeIds = ref<Record<number, number>>({})
const nodeHeading = ref<HTMLElement | null>(null)
const selectedNode = computed(() => {
  const run = props.selected
  return run?.nodes.find(node => node.request_id === selectedNodeIds.value[run.id]) ?? run?.nodes[0] ?? null
})
const selectedNodeIndex = computed(() => props.selected?.nodes.findIndex(node => node.request_id === selectedNode.value?.request_id) ?? -1)
const resultCount = computed(() => props.selected?.nodes.filter(node => node.result !== null).length ?? 0)
const metricMax = computed(() => Math.max(1, ...(props.selected?.nodes.map(node => node[metric.value] ?? 0) ?? [])))

function selectNode(runId: number, requestId: number): void {
  selectedNodeIds.value[runId] = requestId
}
async function stepNode(offset: number): Promise<void> {
  const run = props.selected
  const nextNode = run?.nodes[selectedNodeIndex.value + offset]
  if (!run || !nextNode) return
  selectNode(run.id, nextNode.request_id)
  await nextTick()
  nodeHeading.value?.focus({ preventScroll: true })
  nodeHeading.value?.scrollIntoView({ block: 'start', behavior: 'auto' })
}
function label(key: string): string { return labels[key] ?? key }
function nodeName(type: string): string { return WORKFLOW_NODE_TEMPLATES.find(item => item.nodeType === type)?.name ?? type }
function time(value: string): string { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function duration(value: number | null): string {
  return value === null ? '待统计' : `${(value / 1000).toFixed(1)} 秒`
}
function usage(value: number | null): string {
  return value === null ? '待统计' : `${value.toLocaleString('zh-CN')} tokens`
}
function metricLabel(node: WorkflowRunNodeResponse): string {
  return metric.value === 'latency_ms' ? duration(node.latency_ms) : usage(node.total_tokens)
}
function metricWidth(node: WorkflowRunNodeResponse): string {
  return `${Math.max(0, node[metric.value] ?? 0) / metricMax.value * 100}%`
}
async function copyResult(value: JsonValue): Promise<void> {
  try {
    await navigator.clipboard.writeText(JSON.stringify(value, null, 2))
    ElMessage.success('节点结果已复制')
  } catch {
    ElMessage.error('复制失败，请选择文本后手动复制')
  }
}
</script>

<template>
  <section class="workflow-execution" aria-labelledby="workflow-execution-title">
    <header class="workflow-execution__heading">
      <div>
        <h2 id="workflow-execution-title">AI 运行与结果</h2>
        <p>选择一条运行记录，再打开其中的节点，查看对应分析与建议。生成结果会保存在运行记录中。</p>
      </div>
      <label class="field">
        运行范围
        <select :value="mode" :disabled="busy" @change="emit('update:mode', ($event.target as HTMLSelectElement).value as WorkflowRunMode)">
          <option value="incomplete">继续未完成的节点</option>
          <option value="all">重新运行全部节点</option>
        </select>
      </label>
      <button class="secondary-command" type="button" :disabled="loading" @click="emit('refresh')">{{ loading ? '正在刷新…' : '刷新运行记录' }}</button>
    </header>
    <ul v-if="blockers.length" class="workflow-validation-list" aria-label="运行前检查">
      <li v-for="blocker in blockers" :key="blocker">{{ blocker }}</li>
    </ul>
    <p v-if="busy" role="status" class="workflow-execution__notice">AI 正在处理，节点结果会陆续出现。请勿重复发起；离开页面后可回来查看运行记录。</p>
    <p v-if="mode === 'all' && !busy" class="muted-copy">全部重跑会再次调用模型并产生用量；之前的运行记录会保留。</p>
    <p v-if="error" role="alert" class="inline-alert is-error">{{ error }}</p>
    <div v-if="runs.length" class="workflow-execution__body">
      <nav class="workflow-run-history" aria-label="运行历史">
        <h3>运行记录 <span>本页 {{ runs.length }} 条</span></h3>
        <div v-for="run in runs" :key="run.id" class="workflow-run-entry" :class="{ 'is-selected': selected?.id === run.id }">
          <button class="workflow-run-entry__trigger" type="button" :aria-expanded="selected?.id === run.id"
            :aria-controls="selected?.id === run.id ? `workflow-run-nodes-${run.id}` : undefined" @click="emit('select', run.id)">
            <span class="workflow-run-entry__title"><strong>运行 #{{ run.id }}</strong><span class="workflow-run-status" :data-status="run.status">{{ label(run.status) }}</span></span>
            <time :datetime="run.created_at">{{ time(run.created_at) }}</time>
            <span class="workflow-run-entry__count">{{ run.nodes.length }} 个节点<span aria-hidden="true">{{ selected?.id === run.id ? '已展开' : '点击查看节点' }}</span></span>
          </button>
          <ol v-if="selected?.id === run.id" :id="`workflow-run-nodes-${run.id}`" class="workflow-run-node-list" :aria-label="`运行 #${run.id} 的节点`">
            <li v-for="(node, index) in run.nodes" :key="node.request_id">
              <button type="button" :aria-pressed="selectedNode?.request_id === node.request_id" aria-controls="workflow-selected-node" @click="selectNode(run.id, node.request_id)">
                <span class="workflow-run-node-list__number">{{ index + 1 }}</span>
                <span class="workflow-run-node-list__copy"><strong>{{ nodeName(node.node_type) }}</strong><small>{{ label(node.status) }} · {{ duration(node.latency_ms) }}</small></span>
                <span class="workflow-node-status-dot" :data-status="node.status" aria-hidden="true" />
              </button>
            </li>
          </ol>
        </div>
        <div v-if="totalPages > 1" class="workflow-run-pagination">
          <button type="button" :disabled="page <= 1 || loading || busy" @click="emit('refresh', page - 1)">上一页</button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button type="button" :disabled="page >= totalPages || loading || busy" @click="emit('refresh', page + 1)">下一页</button>
        </div>
      </nav>
      <div v-if="selected" class="workflow-run-results">
        <header class="workflow-run-overview">
          <div><h3>运行 #{{ selected.id }} <span class="workflow-run-status" :data-status="selected.status">{{ label(selected.status) }}</span></h3><p>{{ time(selected.created_at) }} · Context v{{ selected.context_version }}</p></div>
          <p class="workflow-run-overview__count">已有结果 <strong>{{ resultCount }}<span> / {{ selected.nodes.length }}</span></strong></p>
        </header>
        <p v-if="selected.error" role="alert" class="inline-alert is-error">{{ selected.error.message }} {{ errorHints[selected.error.code] || '请检查节点配置，或刷新运行记录后重试。' }}（{{ selected.error.code }}）</p>
        <details v-if="selected.nodes.length" class="workflow-run-chart">
          <summary>节点运行统计 <span>查看耗时与用量</span></summary>
          <div class="workflow-run-chart__heading"><p>{{ metric === 'latency_ms' ? '各节点调用耗时' : '各节点 Token 用量' }}</p><label>统计指标<select v-model="metric"><option value="latency_ms">耗时</option><option value="total_tokens">Token 用量</option></select></label></div>
          <ol class="workflow-run-chart__rows" :aria-label="metric === 'latency_ms' ? '各节点调用耗时' : '各节点 Token 用量'">
            <li v-for="(node, index) in selected.nodes" :key="node.request_id">
              <span>{{ index + 1 }}. {{ nodeName(node.node_type) }}</span><span class="workflow-run-chart__track" aria-hidden="true"><span :style="{ width: metricWidth(node) }" /></span><strong>{{ metricLabel(node) }}</strong>
            </li>
          </ol>
        </details>
        <p v-if="!selected.nodes.length" class="workflow-execution__empty">本次运行尚未生成节点记录，刷新后可查看最新状态。</p>
        <article v-if="selectedNode" id="workflow-selected-node" :key="selectedNode.request_id" class="workflow-node-result" aria-labelledby="workflow-selected-node-title">
          <header class="workflow-node-result__heading">
            <div><p class="workflow-node-result__position">节点 {{ selectedNodeIndex + 1 }} / {{ selected.nodes.length }}</p><h4 id="workflow-selected-node-title" ref="nodeHeading" tabindex="-1">{{ nodeName(selectedNode.node_type) }}</h4></div>
            <div class="workflow-node-result__actions">
              <span class="workflow-run-status" :data-status="selectedNode.status">{{ label(selectedNode.status) }}</span>
              <button v-if="selectedNode.result" class="secondary-command" type="button" @click="copyResult(selectedNode.result)">复制结果</button>
            </div>
          </header>
          <div class="workflow-node-result__metadata"><span>耗时 <strong>{{ duration(selectedNode.latency_ms) }}</strong></span><span>用量 <strong>{{ usage(selectedNode.total_tokens) }}</strong></span><details><summary>节点标识</summary><code>{{ selectedNode.node_key }}</code></details></div>
          <p v-if="selectedNode.error" role="alert" class="inline-alert is-error">{{ selectedNode.error.message }} {{ errorHints[selectedNode.error.code] || '' }}（{{ selectedNode.error.code }}）</p>
          <p v-if="selectedNode.node_type === 'answer_review'" class="muted-copy">静态评审建议，代码未执行，不代表自动判题通过。</p>
          <WorkflowNodeResultContent v-if="selectedNode.result" :result="selectedNode.result" />
          <p v-else-if="selectedNode.status === 'running' || selectedNode.status === 'pending'" class="workflow-node-result__empty" role="status">{{ selectedNode.status === 'running' ? '正在生成此节点的结果，完成后会自动更新。' : '此节点正在等待处理，结果会在运行后显示。' }}</p>
          <p v-else class="workflow-node-result__empty">{{ selectedNode.status === 'failed' ? '此节点未能生成结果。可查看错误原因，再继续运行未完成的节点。' : selectedNode.status === 'cancelled' ? '此节点已中止，没有可展示的结果。' : '此节点已完成，但没有可展示的结构化结果。' }}</p>
          <footer v-if="selected.nodes.length > 1" class="workflow-node-result__pagination">
            <button class="text-command" type="button" :disabled="selectedNodeIndex <= 0" @click="stepNode(-1)">上一个节点</button>
            <span>{{ selectedNodeIndex + 1 }} / {{ selected.nodes.length }}</span>
            <button class="text-command" type="button" :disabled="selectedNodeIndex >= selected.nodes.length - 1" @click="stepNode(1)">下一个节点</button>
          </footer>
        </article>
      </div>
    </div>
    <p v-else-if="!loading" class="workflow-execution__empty">还没有运行记录。添加节点并应用配置后，点击上方“运行 AI”。练习题可以先添加“解题提示”；讲解和评审需要填写代码。</p>
  </section>
</template>
