<script setup lang="ts">
import { ElMessage } from 'element-plus'

import { WORKFLOW_NODE_TEMPLATES } from '@/domain/workflow'
import type { JsonValue, WorkflowRunResponse, WorkflowRunMode } from '@/types/workflow'

defineProps<{
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
  hints: '渐进提示', concepts: '知识点', next_step: '下一步', steps: '逐步讲解',
  complexity: '复杂度', pitfalls: '容易出错的地方', verdict: '静态评审结论', strengths: '做得好的地方',
  issues: '待改进问题', suggested_tests: '建议自己运行的测试', requirements: '需求', features: '功能',
  constraints: '约束', language: '语言', framework: '框架', frontend: '前端', backend: '后端',
  database: '数据库', style: '架构风格', components: '组件职责', data_flows: '数据流', decisions: '设计决策',
  title: '目标', description: '说明', acceptance_criteria: '验收要求', value: '选择', reason: '理由',
  name: '名称', responsibility: '职责', technology: '技术', dependencies: '依赖', source: '来源', target: '目标', data: '数据', choice: '方案',
  looks_correct: '静态阅读暂未发现明显问题，仍需自测', needs_revision: '需要修改', insufficient_information: '信息不足',
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
function label(key: string): string { return labels[key] ?? key }
function nodeName(type: string): string { return WORKFLOW_NODE_TEMPLATES.find(item => item.nodeType === type)?.name ?? type }
function time(value: string): string { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function format(value: JsonValue): string {
  if (value === null) return '未提供'
  if (Array.isArray(value)) return value.length ? value.map((item, i) => `${i + 1}. ${format(item)}`).join('\n') : '无'
  if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${label(key)}：${format(item)}`).join('\n')
  return typeof value === 'string' ? label(value) : String(value)
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
        <p>运行时会保存画布，读取已确认的项目 Context，并同步调用已配置的 AI。成功结果可在刷新后继续查看。</p>
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
        <button v-for="run in runs" :key="run.id" type="button" :aria-pressed="selected?.id === run.id" @click="emit('select', run.id)">
          <strong>运行 #{{ run.id }} · {{ label(run.status) }}</strong>
          <span>{{ time(run.created_at) }}</span>
        </button>
        <div v-if="totalPages > 1" class="workflow-run-pagination">
          <button type="button" :disabled="page <= 1 || loading || busy" @click="emit('refresh', page - 1)">上一页</button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button type="button" :disabled="page >= totalPages || loading || busy" @click="emit('refresh', page + 1)">下一页</button>
        </div>
      </nav>
      <div v-if="selected" class="workflow-run-results" aria-live="polite">
        <h3>运行 #{{ selected.id }} · {{ label(selected.status) }}</h3>
        <p v-if="selected.error" role="alert" class="inline-alert is-error">{{ selected.error.message }} {{ errorHints[selected.error.code] || '请检查节点配置，或刷新运行记录后重试。' }}（{{ selected.error.code }}）</p>
        <p v-if="!selected.nodes.length" class="muted-copy">本次运行尚未生成节点结果。</p>
        <article v-for="node in selected.nodes" :key="node.request_id" class="workflow-node-result">
          <header>
            <h4>{{ nodeName(node.node_type) }}</h4>
            <div class="workflow-node-result__actions">
              <span>{{ label(node.status) }}</span>
              <button v-if="node.result" class="text-command" type="button" @click="copyResult(node.result)">复制结果</button>
            </div>
          </header>
          <small>节点 {{ node.node_key }} · {{ node.latency_ms === null ? '耗时待统计' : `${(node.latency_ms / 1000).toFixed(1)} 秒` }} · {{ node.total_tokens === null ? '用量待统计' : `${node.total_tokens} tokens` }}</small>
          <p v-if="node.error" role="alert">{{ node.error.message }} {{ errorHints[node.error.code] || '' }}</p>
          <p v-if="node.node_type === 'answer_review'" class="muted-copy">静态评审建议，代码未执行，不代表自动判题通过。</p>
          <template v-if="node.result">
            <p class="workflow-node-summary">{{ node.result.summary }}</p>
            <dl>
              <template v-for="(value, key) in node.result" :key="key">
                <div v-if="key !== 'summary' && key !== 'result_type'" class="workflow-result-section">
                  <dt>{{ label(String(key)) }}</dt>
                  <dd>{{ format(value) }}</dd>
                </div>
              </template>
            </dl>
          </template>
        </article>
      </div>
    </div>
    <p v-else-if="!loading" class="workflow-execution__empty">还没有运行记录。添加节点并应用配置后，点击上方“运行 AI”。练习题可以先添加“解题提示”；讲解和评审需要填写代码。</p>
  </section>
</template>
