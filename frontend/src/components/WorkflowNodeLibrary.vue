<script setup lang="ts">
import { WORKFLOW_NODE_TEMPLATES } from '@/domain/workflow'
import type { WorkflowNodeTemplate } from '@/domain/workflow'

defineProps<{
  disabled: boolean
}>()

const emit = defineEmits<{
  add: [template: WorkflowNodeTemplate]
}>()
</script>

<template>
  <aside class="workflow-node-library">
    <div class="workflow-panel-heading">
      <h2>节点库</h2>
      <span>{{ WORKFLOW_NODE_TEMPLATES.length }} 类</span>
    </div>
    <div class="workflow-node-library__list">
      <button
        v-for="template in WORKFLOW_NODE_TEMPLATES"
        :key="template.nodeType"
        type="button"
        :disabled="disabled"
        :class="`is-${template.tone}`"
        @click="emit('add', template)"
      >
        <strong>{{ template.name }}</strong>
        <small>{{ template.description }}</small>
        <span>添加到画布</span>
      </button>
    </div>
  </aside>
</template>
