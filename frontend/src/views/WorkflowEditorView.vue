<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Connection } from '@vue-flow/core'
import { onBeforeRouteLeave, useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { findProjectContext } from '@/api/workflowContext'
import WorkflowCanvas from '@/components/WorkflowCanvas.vue'
import WorkflowNodeConfigPanel from '@/components/WorkflowNodeConfigPanel.vue'
import WorkflowNodeLibrary from '@/components/WorkflowNodeLibrary.vue'
import WorkflowResultPanel from '@/components/WorkflowResultPanel.vue'
import WorkflowToolbar from '@/components/WorkflowToolbar.vue'
import WorkflowExecutionPanel from '@/components/WorkflowExecutionPanel.vue'
import { useWorkflowExecution } from '@/composables/useWorkflowExecution'
import '@/styles/workflow-execution.css'
import {
  createCanvasEdge,
  createCanvasNode,
  graphToCanvas,
  toGraphUpdateInput,
  validateWorkflowGraph,
  EXECUTABLE_NODE_TYPES,
} from '@/domain/workflow'
import type {
  WorkflowCanvasEdge,
  WorkflowCanvasNode,
  WorkflowCanvasNodeData,
  WorkflowNodeTemplate,
} from '@/domain/workflow'
import { useWorkflowStore } from '@/stores/workflows'
import type { ProjectContextResponse } from '@/types/ai'
import type { WorkflowStatus, WorkflowRunMode } from '@/types/workflow'

const route = useRoute()
const workflowStore = useWorkflowStore()
const workflowId = Number(route.params.id)
const { runs, selectedId, selected, page: runPage, totalPages: runTotalPages,
  loading: runsLoading, busy: running, error: runError, refresh: refreshRuns, start: startRun } = useWorkflowExecution(workflowId)
const runMode = ref<WorkflowRunMode>('incomplete')
const configDirty = ref(false)
const preparing = ref(false)
const locked = computed(() => running.value || preparing.value || workflowStore.saving)
const workflowContext = ref<ProjectContextResponse | null>(null)
const contextChecked = ref(false)
const contextLoading = ref(false)
const contextError = ref<string | null>(null)
let mounted = true
const nodes = ref<WorkflowCanvasNode[]>([])
const edges = ref<WorkflowCanvasEdge[]>([])
const workflowName = ref('')
const workflowStatus = ref<WorkflowStatus>('draft')
const savedName = ref('')
const dirty = ref(false)
const selectedNodeId = ref<string | null>(null)
const selectedEdgeId = ref<string | null>(null)

const graphErrors = computed(() => {
  const errors = validateWorkflowGraph(nodes.value, edges.value)
  if (workflowStatus.value === 'ready' && nodes.value.length === 0) {
    errors.push('就绪工作流至少需要一个节点')
  }
  if (!workflowName.value.trim()) errors.push('工作流名称不能为空')
  return errors
})
const selectedNode = computed(
  () => nodes.value.find((node) => node.id === selectedNodeId.value) ?? null,
)
const selectedEdge = computed(
  () => edges.value.find((edge) => edge.id === selectedEdgeId.value) ?? null,
)
const hasSelection = computed(() => selectedNode.value !== null || selectedEdge.value !== null)
const staleContextNodeNames = computed(() => {
  const staleIds = new Set(workflowContext.value?.stale_node_ids ?? [])
  return nodes.value.filter((node) => node.data.databaseId !== null && staleIds.has(node.data.databaseId)).map((node) => node.data.name)
})
const runBlockers = computed(() => {
  const reasons = [...graphErrors.value]
  if (!contextChecked.value || contextLoading.value) reasons.push('正在检查项目 Context，请稍候。')
  else if (contextError.value) reasons.push('项目 Context 状态读取失败，请刷新后重试。')
  else if (!workflowContext.value) reasons.push('关联项目还没有 Context，请先到 AI 工作台创建。')
  else if (workflowContext.value.is_stale) reasons.push('项目 Context 与项目资料不一致，请先到 AI 工作台同步。')
  if (configDirty.value) reasons.push('节点配置尚未应用，请先点击“应用配置”。')
  if (!nodes.value.length) reasons.push('请先添加一个 AI 节点。')
  for (const node of nodes.value) {
    if (!EXECUTABLE_NODE_TYPES.has(node.data.nodeType)) reasons.push(`“${node.data.name}”暂不支持 AI 执行，请移除或更换节点类型。`)
    if (['code_explanation', 'answer_review'].includes(node.data.nodeType) &&
        (typeof node.data.config?.student_code !== 'string' || !node.data.config.student_code.trim())) {
      reasons.push(`请在“${node.data.name}”的配置中填写代码。`)
    }
  }
  if (edges.value.some(edge => edge.data.conditionData && Object.keys(edge.data.conditionData).length)) reasons.push('当前执行引擎暂不支持条件连线。')
  return reasons
})

async function loadContext(projectId: number): Promise<boolean> {
  contextLoading.value = true
  contextError.value = null
  try {
    workflowContext.value = await findProjectContext(projectId)
    contextChecked.value = true
    return workflowContext.value !== null && !workflowContext.value.is_stale
  } catch (error: unknown) {
    workflowContext.value = null
    contextChecked.value = true
    contextError.value = getApiErrorMessage(error, '项目 Context 状态读取失败')
    return false
  } finally {
    contextLoading.value = false
  }
}

function applyGraph(): void {
  const graph = workflowStore.currentGraph
  if (!graph) return
  const canvas = graphToCanvas(graph)
  nodes.value = canvas.nodes
  edges.value = canvas.edges
  workflowName.value = graph.workflow.name
  workflowStatus.value = graph.workflow.status
  savedName.value = graph.workflow.name
  selectedNodeId.value = null
  selectedEdgeId.value = null
  dirty.value = false
}

async function load(): Promise<void> {
  if (!Number.isInteger(workflowId) || workflowId < 1) return
  await workflowStore.fetchGraph(workflowId)
  applyGraph()
  const projectId = workflowStore.currentGraph?.workflow.project.id
  await Promise.all([
    refreshRuns(1),
    projectId ? loadContext(projectId) : Promise.resolve(false),
  ])
}

function markDirty(): void {
  dirty.value = true
}

function addNode(template: WorkflowNodeTemplate): void {
  if (locked.value || !canChangeSelection()) return
  if (nodes.value.length >= 100) {
    ElMessage.warning('节点数量不能超过 100 个')
    return
  }
  const node = createCanvasNode(template, nodes.value.length)
  nodes.value = [...nodes.value, node]
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
  markDirty()
}

function connect(connection: Connection): void {
  if (locked.value || !canChangeSelection()) return
  const candidate = createCanvasEdge(connection.source, connection.target)
  const nextEdges = [...edges.value, candidate]
  const errors = validateWorkflowGraph(nodes.value, nextEdges)
  if (errors.length > 0) {
    ElMessage.warning(errors[0])
    return
  }
  edges.value = nextEdges
  selectedEdgeId.value = candidate.id
  selectedNodeId.value = null
  markDirty()
}

function canChangeSelection(): boolean {
  if (!configDirty.value) return true
  ElMessage.warning('请先应用当前节点的配置，再切换选择。')
  return false
}

function selectNode(nodeId: string): void {
  if (nodeId !== selectedNodeId.value && !canChangeSelection()) return
  selectedNodeId.value = nodeId
  selectedEdgeId.value = null
}

function selectEdge(edgeId: string): void {
  if (!canChangeSelection()) return
  selectedEdgeId.value = edgeId
  selectedNodeId.value = null
}

function clearSelection(): void {
  if (!canChangeSelection()) return
  selectedNodeId.value = null
  selectedEdgeId.value = null
}

function moveNode(nodeId: string, x: number, y: number): void {
  if (locked.value) return
  nodes.value = nodes.value.map((node) => (
    node.id === nodeId ? { ...node, position: { x, y } } : node
  ))
  markDirty()
}

function updateNode(nodeId: string, data: WorkflowCanvasNodeData): void {
  if (locked.value) return
  nodes.value = nodes.value.map((node) => (
    node.id === nodeId ? { ...node, ariaLabel: data.name, data } : node
  ))
  markDirty()
}

function deleteNode(nodeId: string): void {
  if (locked.value) return
  configDirty.value = false
  nodes.value = nodes.value.filter((node) => node.id !== nodeId)
  edges.value = edges.value.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
  clearSelection()
  markDirty()
}

function deleteEdge(edgeId: string): void {
  if (locked.value) return
  edges.value = edges.value.filter((edge) => edge.id !== edgeId)
  clearSelection()
  markDirty()
}

function deleteSelection(): void {
  if (selectedNodeId.value) deleteNode(selectedNodeId.value)
  else if (selectedEdgeId.value) deleteEdge(selectedEdgeId.value)
}

function updateName(name: string): void {
  workflowName.value = name
  markDirty()
}

async function save(): Promise<boolean> {
  if (!workflowStore.currentGraph || running.value || workflowStore.saving) return false
  if (configDirty.value) {
    ElMessage.warning('请先应用当前节点的配置，再保存工作流。')
    return false
  }
  if (graphErrors.value.length > 0) {
    ElMessage.warning(graphErrors.value[0])
    return false
  }
  try {
    const version = workflowStore.currentGraph.workflow.version
    await workflowStore.saveGraph(
      workflowId,
      toGraphUpdateInput(version, nodes.value, edges.value),
    )
    if (workflowName.value.trim() !== savedName.value) {
      await workflowStore.updateWorkflow(workflowId, {
        name: workflowName.value.trim(),
      })
    }
    applyGraph()
    ElMessage.success('工作流已保存')
    return true
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '工作流保存失败'))
    return false
  }
}

async function run(): Promise<void> {
  if (locked.value || runsLoading.value || runBlockers.value.length || !workflowStore.currentGraph) return
  preparing.value = true
  try {
    if (dirty.value && !(await save())) return
    const workflow = workflowStore.currentGraph.workflow
    if (!(await loadContext(workflow.project.id))) {
      ElMessage.warning(workflowContext.value?.is_stale ? '请先同步项目 Context' : '请先处理项目 Context')
      return
    }
    await startRun(workflow.version, runMode.value)
  } finally {
    preparing.value = false
  }
}

watch(running, async (value, previous) => {
  if (previous && !value && !dirty.value && !configDirty.value) {
    try {
      await workflowStore.fetchGraph(workflowId)
      if (mounted) {
        applyGraph()
        const projectId = workflowStore.currentGraph?.workflow.project.id
        if (projectId) await loadContext(projectId)
      }
    } catch { /* 加载错误由 Store 的图错误面板展示。 */ }
  }
})

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value && !configDirty.value) return
  event.preventDefault()
}

onBeforeRouteLeave(() => {
  if (!dirty.value && !configDirty.value) return true
  return window.confirm('工作流还有未保存修改，确定离开吗？')
})

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  void load().catch(() => undefined)
})

onUnmounted(() => {
  mounted = false
  window.removeEventListener('beforeunload', beforeUnload)
  workflowStore.clearCurrentGraph()
})
</script>

<template>
  <section class="workflow-editor-page">
    <div v-if="workflowStore.graphError" class="state-panel state-panel--error workflow-editor-state">
      <strong>工作流加载失败</strong>
      <p>{{ workflowStore.graphError }}</p>
      <button class="secondary-command" type="button" @click="load">重试</button>
    </div>
    <div v-else-if="workflowStore.graphLoading || !workflowStore.currentGraph" class="workflow-editor-loading" aria-label="工作流加载中">
      <span /><span /><span />
    </div>
    <template v-else>
      <WorkflowToolbar
        :name="workflowName"
        :status="workflowStatus"
        :version="workflowStore.currentGraph.workflow.version"
        :dirty="dirty || configDirty"
        :saving="workflowStore.saving"
        :running="locked"
        :run-disabled="runBlockers.length > 0 || runsLoading"
        :has-selection="hasSelection"
        @update:name="updateName"
        @run="run"
        @save="save"
        @delete-selection="deleteSelection"
      />
      <section class="workflow-context-status" :data-state="contextError ? 'error' : !workflowContext ? 'missing' : workflowContext.is_stale ? 'stale' : 'ready'" aria-live="polite">
        <div>
          <strong v-if="contextLoading || !contextChecked">正在检查项目 Context…</strong>
          <strong v-else-if="contextError">Context 状态读取失败</strong>
          <strong v-else-if="!workflowContext">运行前需要创建项目 Context</strong>
          <strong v-else-if="workflowContext.is_stale">Context 与项目资料不一致</strong>
          <strong v-else>Context v{{ workflowContext.version }} 可用于运行</strong>
          <p v-if="contextError">{{ contextError }}</p>
          <p v-else-if="workflowContext?.is_stale">待同步字段：{{ workflowContext.stale_fields.join('、') }}</p>
          <p v-else-if="staleContextNodeNames.length">受 Context 更新影响：{{ staleContextNodeNames.join('、') }}。选择“继续未完成的节点”即可重新生成。</p>
          <p v-else>页面只读取当前版本；不会自动同步资料或发起付费调用。</p>
        </div>
        <RouterLink class="secondary-command" :to="`/projects/${workflowStore.currentGraph.workflow.project.id}/ai`">管理 Context 与 AI</RouterLink>
      </section>
      <div class="workflow-editor-grid">
        <WorkflowNodeLibrary :disabled="locked" @add="addNode" />
        <WorkflowCanvas
          :nodes="nodes"
          :edges="edges"
          :disabled="locked || configDirty"
          @update:nodes="nodes = $event"
          @update:edges="edges = $event"
          @connect="connect"
          @node-selected="selectNode"
          @edge-selected="selectEdge"
          @selection-cleared="clearSelection"
          @node-moved="moveNode"
        />
        <aside class="workflow-inspector">
          <WorkflowNodeConfigPanel :node="selectedNode" :disabled="locked" @pending-change="configDirty = $event" @update="updateNode" @delete="deleteNode" />
          <WorkflowResultPanel
            :nodes="nodes"
            :edges="edges"
            :errors="graphErrors"
            :selected-edge="selectedEdge"
            @delete-edge="deleteEdge"
          />
        </aside>
      </div>
      <WorkflowExecutionPanel :runs="runs" :selected="selected" :loading="runsLoading" :busy="locked"
        :error="runError" :blockers="runBlockers" :mode="runMode" :page="runPage" :total-pages="runTotalPages"
        @refresh="refreshRuns" @select="selectedId = $event" @update:mode="runMode = $event" />
    </template>
  </section>
</template>
