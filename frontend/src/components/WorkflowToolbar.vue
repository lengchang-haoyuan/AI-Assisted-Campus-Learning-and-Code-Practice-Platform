<script setup lang="ts">
import { WORKFLOW_STATUS_LABELS } from '@/domain/workflow'
import type { WorkflowStatus } from '@/types/workflow'

defineProps<{
  name: string
  status: WorkflowStatus
  version: number
  dirty: boolean
  saving: boolean
  hasSelection: boolean
  running: boolean
  runDisabled: boolean
}>()

const emit = defineEmits<{
  'update:name': [name: string]
  save: []
  'delete-selection': []
  run: []
}>()
</script>

<template>
  <header class="workflow-toolbar">
    <RouterLink class="text-command" to="/workflows">返回工作流</RouterLink>
    <label class="workflow-toolbar__name">
      <span class="sr-only">工作流名称</span>
      <input
        :value="name"
        :disabled="running"
        maxlength="120"
        aria-label="工作流名称"
        @input="emit('update:name', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <span class="workflow-toolbar__status" aria-label="工作流状态">{{ running ? 'AI 运行中' : WORKFLOW_STATUS_LABELS[status] }}</span>
    <span class="workflow-version">v{{ version }}</span>
    <span class="workflow-save-state" :class="{ 'is-dirty': dirty }">
      {{ dirty ? '有未保存修改' : '已保存' }}
    </span>
    <button
      class="secondary-command"
      type="button"
      :disabled="!hasSelection || saving || running"
      @click="emit('delete-selection')"
    >
      删除所选
    </button>
    <button class="secondary-command" type="button" :disabled="saving || running || !dirty" @click="emit('save')">
      {{ saving ? '保存中…' : '保存工作流' }}
    </button>
    <button class="primary-command" type="button" :disabled="runDisabled || running || saving" @click="emit('run')">
      {{ running ? 'AI 运行中…' : dirty ? '保存并运行 AI' : '运行 AI' }}
    </button>
  </header>
</template>
