<script setup lang="ts">
import type { WorkflowCanvasEdge, WorkflowCanvasNode } from '@/domain/workflow'

defineProps<{
  nodes: WorkflowCanvasNode[]
  edges: WorkflowCanvasEdge[]
  errors: string[]
  selectedEdge: WorkflowCanvasEdge | null
}>()

const emit = defineEmits<{
  'delete-edge': [edgeId: string]
}>()
</script>

<template>
  <section class="workflow-result-panel">
    <div class="workflow-panel-heading">
      <h2>图检查</h2>
      <span :class="errors.length ? 'is-invalid' : 'is-valid'">
        {{ errors.length ? `${errors.length} 项问题` : '结构有效' }}
      </span>
    </div>
    <div class="workflow-graph-metrics">
      <div><strong>{{ nodes.length }}</strong><span>节点</span></div>
      <div><strong>{{ edges.length }}</strong><span>连线</span></div>
    </div>
    <ul v-if="errors.length" class="workflow-validation-list">
      <li v-for="error in errors" :key="error">{{ error }}</li>
    </ul>
    <p v-else class="workflow-validation-ok">节点引用、重复边、自环和循环检查通过。</p>
    <div v-if="selectedEdge" class="workflow-selected-edge">
      <span>当前连线</span>
      <strong>{{ selectedEdge.source }} → {{ selectedEdge.target }}</strong>
      <button class="danger-command" type="button" @click="emit('delete-edge', selectedEdge.id)">删除连线</button>
    </div>
  </section>
</template>
