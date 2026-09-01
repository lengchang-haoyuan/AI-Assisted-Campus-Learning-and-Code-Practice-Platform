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
}>()

const emit = defineEmits<{
  'update:name': [name: string]
  'update:status': [status: WorkflowStatus]
  save: []
  'delete-selection': []
}>()
</script>

<template>
  <header class="workflow-toolbar">
    <RouterLink class="text-command" to="/workflows">返回工作流</RouterLink>
    <label class="workflow-toolbar__name">
      <span class="sr-only">工作流名称</span>
      <input
        :value="name"
        maxlength="120"
        aria-label="工作流名称"
        @input="emit('update:name', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <label class="workflow-toolbar__status">
      <span class="sr-only">工作流状态</span>
      <select
        :value="status"
        aria-label="工作流状态"
        @change="emit('update:status', ($event.target as HTMLSelectElement).value as WorkflowStatus)"
      >
        <option v-for="(label, value) in WORKFLOW_STATUS_LABELS" :key="value" :value="value">
          {{ label }}
        </option>
      </select>
    </label>
    <span class="workflow-version">v{{ version }}</span>
    <span class="workflow-save-state" :class="{ 'is-dirty': dirty }">
      {{ dirty ? '有未保存修改' : '已保存' }}
    </span>
    <button
      class="secondary-command"
      type="button"
      :disabled="!hasSelection || saving"
      @click="emit('delete-selection')"
    >
      删除所选
    </button>
    <button class="primary-command" type="button" :disabled="saving || !dirty" @click="emit('save')">
      {{ saving ? '保存中…' : '保存工作流' }}
    </button>
  </header>
</template>
