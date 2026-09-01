<script setup lang="ts">
import { computed } from 'vue'
import {
  ConnectionMode,
  VueFlow,
  useVueFlow,
} from '@vue-flow/core'
import type {
  Connection,
  EdgeMouseEvent,
  NodeDragEvent,
  NodeMouseEvent,
} from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

import WorkflowNodeCard from '@/components/WorkflowNodeCard.vue'
import type { WorkflowCanvasEdge, WorkflowCanvasNode } from '@/domain/workflow'

const props = defineProps<{
  nodes: WorkflowCanvasNode[]
  edges: WorkflowCanvasEdge[]
}>()

const emit = defineEmits<{
  'update:nodes': [nodes: WorkflowCanvasNode[]]
  'update:edges': [edges: WorkflowCanvasEdge[]]
  connect: [connection: Connection]
  'node-selected': [nodeId: string]
  'edge-selected': [edgeId: string]
  'selection-cleared': []
  'node-moved': [nodeId: string, x: number, y: number]
}>()

const nodesModel = computed({
  get: () => props.nodes,
  set: (nodes: WorkflowCanvasNode[]) => emit('update:nodes', nodes),
})
const edgesModel = computed({
  get: () => props.edges,
  set: (edges: WorkflowCanvasEdge[]) => emit('update:edges', edges),
})
const shouldFitViewOnInit = props.nodes.length > 0
const { fitView, zoomIn, zoomOut } = useVueFlow()

function selectNode(event: NodeMouseEvent): void {
  emit('node-selected', event.node.id)
}

function selectEdge(event: EdgeMouseEvent): void {
  emit('edge-selected', event.edge.id)
}

function finishNodeMove(event: NodeDragEvent): void {
  emit('node-moved', event.node.id, event.node.position.x, event.node.position.y)
}

function zoomCanvasIn(): void {
  void zoomIn()
}

function zoomCanvasOut(): void {
  void zoomOut()
}

function fitCanvas(): void {
  void fitView()
}

function initializeCanvas(): void {
  if (!shouldFitViewOnInit) return
  window.requestAnimationFrame(() => {
    void fitView()
  })
}
</script>

<template>
  <div class="workflow-canvas-shell">
    <VueFlow
      v-model:nodes="nodesModel"
      v-model:edges="edgesModel"
      :connection-mode="ConnectionMode.Strict"
      :min-zoom="0.35"
      :max-zoom="1.8"
      :snap-to-grid="true"
      :snap-grid="[16, 16]"
      :delete-key-code="null"
      class="workflow-canvas"
      @connect="emit('connect', $event)"
      @nodes-initialized="initializeCanvas"
      @node-click="selectNode"
      @edge-click="selectEdge"
      @node-drag-stop="finishNodeMove"
      @pane-click="emit('selection-cleared')"
    >
      <template #node-workflow="nodeProps">
        <WorkflowNodeCard :data="nodeProps.data" :selected="nodeProps.selected" />
      </template>
    </VueFlow>
    <div class="workflow-canvas-controls" aria-label="画布缩放">
      <button type="button" title="放大" aria-label="放大" @click="zoomCanvasIn">+</button>
      <button type="button" title="缩小" aria-label="缩小" @click="zoomCanvasOut">-</button>
      <button type="button" @click="fitCanvas">适应画布</button>
    </div>
  </div>
</template>
