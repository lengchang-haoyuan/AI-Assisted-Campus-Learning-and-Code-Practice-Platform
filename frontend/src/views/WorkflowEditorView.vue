<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Connection } from '@vue-flow/core'
import { onBeforeRouteLeave, useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import WorkflowCanvas from '@/components/WorkflowCanvas.vue'
import WorkflowNodeConfigPanel from '@/components/WorkflowNodeConfigPanel.vue'
import WorkflowNodeLibrary from '@/components/WorkflowNodeLibrary.vue'
import WorkflowResultPanel from '@/components/WorkflowResultPanel.vue'
import WorkflowToolbar from '@/components/WorkflowToolbar.vue'
import {
  createCanvasEdge,
  createCanvasNode,
  graphToCanvas,
  toGraphUpdateInput,
  validateWorkflowGraph,
} from '@/domain/workflow'
import type {
  WorkflowCanvasEdge,
  WorkflowCanvasNode,
  WorkflowCanvasNodeData,
  WorkflowNodeTemplate,
} from '@/domain/workflow'
import { useWorkflowStore } from '@/stores/workflows'
import type { WorkflowStatus } from '@/types/workflow'

const route = useRoute()
const workflowStore = useWorkflowStore()
const workflowId = Number(route.params.id)
const nodes = ref<WorkflowCanvasNode[]>([])
const edges = ref<WorkflowCanvasEdge[]>([])
const workflowName = ref('')
const workflowStatus = ref<WorkflowStatus>('draft')
const savedName = ref('')
const savedStatus = ref<WorkflowStatus>('draft')
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

function applyGraph(): void {
  const graph = workflowStore.currentGraph
  if (!graph) return
  const canvas = graphToCanvas(graph)
  nodes.value = canvas.nodes
  edges.value = canvas.edges
  workflowName.value = graph.workflow.name
  workflowStatus.value = graph.workflow.status
  savedName.value = graph.workflow.name
  savedStatus.value = graph.workflow.status
  selectedNodeId.value = null
  selectedEdgeId.value = null
  dirty.value = false
}

async function load(): Promise<void> {
  if (!Number.isInteger(workflowId) || workflowId < 1) return
  await workflowStore.fetchGraph(workflowId)
  applyGraph()
}

function markDirty(): void {
  dirty.value = true
}

function addNode(template: WorkflowNodeTemplate): void {
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

function selectNode(nodeId: string): void {
  selectedNodeId.value = nodeId
  selectedEdgeId.value = null
}

function selectEdge(edgeId: string): void {
  selectedEdgeId.value = edgeId
  selectedNodeId.value = null
}

function clearSelection(): void {
  selectedNodeId.value = null
  selectedEdgeId.value = null
}

function moveNode(nodeId: string, x: number, y: number): void {
  nodes.value = nodes.value.map((node) => (
    node.id === nodeId ? { ...node, position: { x, y } } : node
  ))
  markDirty()
}

function updateNode(nodeId: string, data: WorkflowCanvasNodeData): void {
  nodes.value = nodes.value.map((node) => (
    node.id === nodeId ? { ...node, ariaLabel: data.name, data } : node
  ))
  markDirty()
}

function deleteNode(nodeId: string): void {
  nodes.value = nodes.value.filter((node) => node.id !== nodeId)
  edges.value = edges.value.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
  clearSelection()
  markDirty()
}

function deleteEdge(edgeId: string): void {
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

function updateStatus(status: WorkflowStatus): void {
  workflowStatus.value = status
  markDirty()
}

async function save(): Promise<void> {
  if (!workflowStore.currentGraph) return
  if (graphErrors.value.length > 0) {
    ElMessage.warning(graphErrors.value[0])
    return
  }
  try {
    const version = workflowStore.currentGraph.workflow.version
    await workflowStore.saveGraph(
      workflowId,
      toGraphUpdateInput(version, nodes.value, edges.value),
    )
    if (workflowName.value.trim() !== savedName.value || workflowStatus.value !== savedStatus.value) {
      await workflowStore.updateWorkflow(workflowId, {
        name: workflowName.value.trim(),
        status: workflowStatus.value,
      })
    }
    applyGraph()
    ElMessage.success('工作流已保存')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '工作流保存失败'))
  }
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (!dirty.value) return
  event.preventDefault()
}

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('工作流还有未保存修改，确定离开吗？')
})

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  void load().catch(() => undefined)
})

onUnmounted(() => {
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
        :dirty="dirty"
        :saving="workflowStore.saving"
        :has-selection="hasSelection"
        @update:name="updateName"
        @update:status="updateStatus"
        @save="save"
        @delete-selection="deleteSelection"
      />
      <div class="workflow-editor-grid">
        <WorkflowNodeLibrary :disabled="workflowStore.saving" @add="addNode" />
        <WorkflowCanvas
          :nodes="nodes"
          :edges="edges"
          @update:nodes="nodes = $event"
          @update:edges="edges = $event"
          @connect="connect"
          @node-selected="selectNode"
          @edge-selected="selectEdge"
          @selection-cleared="clearSelection"
          @node-moved="moveNode"
        />
        <aside class="workflow-inspector">
          <WorkflowNodeConfigPanel :node="selectedNode" @update="updateNode" @delete="deleteNode" />
          <WorkflowResultPanel
            :nodes="nodes"
            :edges="edges"
            :errors="graphErrors"
            :selected-edge="selectedEdge"
            @delete-edge="deleteEdge"
          />
        </aside>
      </div>
    </template>
  </section>
</template>
