<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

import type { WorkflowCanvasNodeData } from '@/domain/workflow'

defineProps<{
  data: WorkflowCanvasNodeData
  selected: boolean
}>()
</script>

<template>
  <div
    class="workflow-node-card"
    :class="[`workflow-node-card--${data.tone}`, { 'is-selected': selected }]"
  >
    <Handle type="target" :position="Position.Left" />
    <span class="workflow-node-card__type">{{ data.nodeType.replaceAll('_', ' ') }}</span>
    <strong>{{ data.name }}</strong>
    <small>{{ typeof data.config?.instruction === 'string' ? data.config.instruction : '等待配置' }}</small>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
