<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { getWorkflowGraph, listWorkflowRuns, listWorkflows } from '@/api/workflows'
import { writeNodeContext } from '@/api/workflowContext'
import { getApiErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { ProjectContextPatch, ProjectContextResponse } from '@/types/ai'
import type { JsonObject, JsonValue, WorkflowGraphResponse, WorkflowResponse, WorkflowRunResponse } from '@/types/workflow'

const props = defineProps<{ context: ProjectContextResponse; draftDirty: boolean }>()
const emit = defineEmits<{ applied: [value: ProjectContextResponse] }>()
const auth = useAuthStore()
const workflows = shallowRef<WorkflowResponse[]>([]), runs = shallowRef<WorkflowRunResponse[]>([])
const graph = shallowRef<WorkflowGraphResponse | null>(null)
const workflowId = ref(''), sourceId = ref(''), workflowPage = ref(1), runPage = ref(1)
const hasWorkflows = ref(false), hasRuns = ref(false), loaded = ref(false), busy = ref(false), acknowledged = ref(false)
const selectedFields = ref<string[]>([]), error = ref<string | null>(null), notice = ref<string | null>(null)
let generation = 0, disposed = false
const labels: Record<string, string> = { requirements: '需求', features: '功能', constraints: '约束', language: '语言', framework: '框架', frontend: '前端', backend: '后端', database: '数据库', architecture: '架构' }
const sources = computed(() => runs.value.flatMap(run => run.nodes.filter(node => node.status === 'completed' && node.result && ['requirements_analysis', 'tech_stack_analysis', 'architecture_design'].includes(node.node_type)).map(node => ({ run, node, key: `${run.id}:${node.request_id}` }))))
const source = computed(() => sources.value.find(item => item.key === sourceId.value))
const sourceNode = computed(() => graph.value?.nodes.find(node => node.id === source.value?.node.node_id && node.node_key === source.value.node.node_key && node.node_type === source.value.node.node_type))
const candidates = computed(() => {
  const result = source.value?.node.result, node = sourceNode.value
  if (!result || !node || result.result_type !== node.node_type) return []
  let values: ProjectContextPatch = {}
  const strings = (value: JsonValue | undefined): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string')
  if (node.node_type === 'tech_stack_analysis') {
    for (const field of ['language', 'framework', 'frontend', 'backend', 'database'] as const) {
      const item = result[field]
      if (item && typeof item === 'object' && !Array.isArray(item) && typeof item.value === 'string') values[field] = item.value
    }
  } else if (node.node_type === 'requirements_analysis') {
    if (Array.isArray(result.requirements) && result.requirements.every(item => item && typeof item === 'object' && !Array.isArray(item))) values.requirements = result.requirements as JsonObject[]
    if (strings(result.features)) values.features = result.features
    if (strings(result.constraints)) values.constraints = result.constraints
  } else if (node.node_type === 'architecture_design') {
    // 原机制对architecture做对象合并。候选只含该节点原Schema的四个结构字段。
    values = { architecture: Object.fromEntries(['style', 'components', 'data_flows', 'decisions'].flatMap(key => result[key] === undefined ? [] : [[key, result[key]]])) }
  }
  const narrowed = node.config?.context_writes
  return Object.entries(values).filter(([key]) => narrowed === undefined || (Array.isArray(narrowed) && narrowed.includes(key))).map(([field, value]) => ({ field: field as keyof ProjectContextPatch, value, current: props.context.values[field as keyof ProjectContextPatch], changed: JSON.stringify(value) !== JSON.stringify(props.context.values[field as keyof ProjectContextPatch]) }))
})
const stale = computed(() => !source.value || !sourceNode.value || source.value.run.context_version !== props.context.version || sourceNode.value.context_version !== props.context.version || sourceNode.value.status !== 'success' || props.context.is_stale)
const canApply = computed(() => !busy.value && !props.draftDirty && !stale.value && acknowledged.value && candidates.value.some(item => selectedFields.value.includes(item.field) && item.changed))
const current = (epoch: number, token: string | null) => !disposed && generation === epoch && auth.token === token
watch(sourceId, () => { selectedFields.value = []; acknowledged.value = false; notice.value = null })
watch(() => props.context.version, () => { selectedFields.value = []; acknowledged.value = false })
async function loadWorkflows(page = 1): Promise<void> {
  const epoch = ++generation, token = auth.token
  busy.value = true; error.value = null
  graph.value = null; runs.value = []; sourceId.value = workflowId.value = ''
  try {
    const result = await listWorkflows({ page, pageSize: 20, projectId: props.context.project_id })
    if (!current(epoch, token)) return
    workflows.value = result.items.filter(item => item.project.id === props.context.project_id)
    workflowPage.value = page; hasWorkflows.value = page < result.total_pages; loaded.value = true
  } catch (cause: unknown) { if (current(epoch, token)) error.value = getApiErrorMessage(cause, '候选来源查询失败。') }
  finally { if (current(epoch, token)) busy.value = false }
}
async function loadRuns(page = 1): Promise<void> {
  const id = Number(workflowId.value), epoch = ++generation, token = auth.token
  if (!workflows.value.some(item => item.id === id)) return
  busy.value = true; error.value = null; sourceId.value = ''; runs.value = []; graph.value = null
  try {
    const [nodes, result] = await Promise.all([getWorkflowGraph(id), listWorkflowRuns(id, page)])
    if (!current(epoch, token) || nodes.workflow.project.id !== props.context.project_id) return
    graph.value = nodes; runs.value = result.items.filter(item => item.workflow_id === id)
    runPage.value = page; hasRuns.value = page < result.total_pages
  } catch (cause: unknown) { if (current(epoch, token)) error.value = getApiErrorMessage(cause, '工作流历史查询失败。') }
  finally { if (current(epoch, token)) busy.value = false }
}
async function apply(): Promise<void> {
  if (!canApply.value || !source.value || !sourceNode.value) return
  const epoch = generation, token = auth.token, id = props.context.project_id, node = sourceNode.value
  const values: ProjectContextPatch = Object.fromEntries(candidates.value.filter(item => selectedFields.value.includes(item.field) && item.changed).map(item => [item.field, item.value]))
  busy.value = true; error.value = notice.value = null
  try {
    const result = await writeNodeContext(node.workflow_id, node.id, props.context.version, values)
    if (!current(epoch, token) || result.context.project_id !== id) return
    emit('applied', result.context)
    notice.value = result.changed_fields.length ? `已应用所选字段，资料为 v${result.context.version}。既有实践快照保持原版本。` : '字段内容一致，版本未变化。'
    acknowledged.value = false; selectedFields.value = []
  } catch (cause: unknown) { if (current(epoch, token)) error.value = getApiErrorMessage(cause, '未确认写回成功。请刷新资料核对；不会自动重试。') }
  finally { if (current(epoch, token)) busy.value = false }
}
onBeforeUnmount(() => { disposed = true; ++generation })
</script>

<template>
  <details class="ai-context-candidates"><summary>AI 候选与字段差异</summary><p>读取旧工作流的确切请求结果。仅展示候选不会写入；实践建议不回写项目资料。</p>
    <p v-if="error" class="inline-alert is-error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <button v-if="!loaded" class="secondary-command" :disabled="busy" @click="loadWorkflows()">查询候选来源（不调用模型）</button>
    <template v-else><div class="ai-candidate-controls"><label class="field"><span>来源工作流</span><select v-model="workflowId" :disabled="busy" @change="loadRuns()"><option value="">选择工作流</option><option v-for="workflow in workflows" :key="workflow.id" :value="workflow.id">{{ workflow.name }}</option></select></label><button class="secondary-command" :disabled="busy || workflowPage === 1" @click="loadWorkflows(workflowPage - 1)">前一页工作流</button><button class="secondary-command" :disabled="busy || !hasWorkflows" @click="loadWorkflows(workflowPage + 1)">后一页工作流</button></div><p v-if="!workflows.length">当前项目暂无工作流候选。可直接进入固定实践。</p>
    <template v-if="graph"><label class="field"><span>确切历史请求</span><select v-model="sourceId" :disabled="busy"><option value="">选择保存的结果</option><option v-for="item in sources" :key="item.key" :value="item.key">运行 #{{ item.run.id }} · {{ item.node.node_key }} · 请求 #{{ item.node.request_id }} · 资料 v{{ item.run.context_version }}</option></select></label><div class="practice-actions"><button class="secondary-command" :disabled="busy || runPage === 1" @click="loadRuns(runPage - 1)">前一页运行</button><button class="secondary-command" :disabled="busy || !hasRuns" @click="loadRuns(runPage + 1)">后一页运行</button></div><p v-if="!sources.length">本页无可应用结果；讲解、评审和提示节点没有项目写权限。</p></template>
    <template v-if="source"><p>{{ source.node.result?.summary }}</p><p v-if="stale" class="inline-alert">该结果版本或节点状态已过期，仅供参考，不能写回当前资料。</p><p v-if="draftDirty">本页还有草稿或正在保存，请先处理后再选择候选。</p><div class="ai-candidate-diff" v-for="item in candidates" :key="item.field"><label><input v-model="selectedFields" type="checkbox" :value="item.field" :disabled="busy || stale || draftDirty || !item.changed" />{{ labels[item.field] }}{{ item.changed ? '' : ' · 内容一致' }}</label><div><section><strong>当前已定</strong><pre tabindex="0">{{ JSON.stringify(item.current, null, 2) }}</pre></section><section><strong>候选建议</strong><pre tabindex="0">{{ JSON.stringify(item.value, null, 2) }}</pre></section></div></div><p v-if="source.node.node_type === 'architecture_design'">架构使用原有对象合并规则，未列出的现有键会保留。</p><label class="ai-candidate-ack"><input v-model="acknowledged" type="checkbox" :disabled="busy || stale || draftDirty" />我已核对来源与差异，仅应用勾选字段</label><button class="primary-command" :disabled="!canApply" @click="apply">应用所选候选</button><details><summary>来源引用</summary><p>工作流 {{ workflowId }} / 运行 {{ source.run.id }} / 节点 {{ source.node.node_id }} / 请求 {{ source.node.request_id }}</p></details></template></template>
  </details>
</template>

<style scoped>
.ai-context-candidates { margin-top: 24px; padding: 20px 0; border-block: 1px solid var(--line); }
summary { cursor: pointer; font-weight: 750; padding: 10px 0; }
p { line-height: 1.8; }
.ai-candidate-controls { display: flex; flex-wrap: wrap; align-items: end; gap: 10px; margin: 16px 0; }
.ai-candidate-controls .field { flex: 1; min-width: 180px; }
.ai-candidate-diff { margin-block: 20px; padding-block: 16px; border-top: 1px dashed var(--line); }
.ai-candidate-diff > div { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
.ai-candidate-diff section { min-width: 0; }
pre { max-height: 240px; padding: 12px; overflow: auto; background: #eff5ef; font: 13px/1.8 Consolas, monospace; }
input { margin-right: 9px; accent-color: #22755e; }
.ai-candidate-ack { display: block; margin-block: 18px; line-height: 1.8; }
@media(max-width: 620px) { .ai-candidate-diff > div { grid-template-columns: 1fr; } }
</style>
