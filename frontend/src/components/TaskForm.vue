<script setup lang="ts">
import { reactive, ref } from 'vue'

import { getLocalDateValue } from '@/domain/workspace'
import type { ProjectResponse } from '@/types/project'
import type { TaskCreateInput, TaskPriority } from '@/types/workspace'

defineProps<{
  projects: ProjectResponse[]
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: TaskCreateInput]
  cancel: []
}>()

const form = reactive({
  title: '',
  description: '',
  priority: 'medium' as TaskPriority,
  scheduledDate: getLocalDateValue(),
  startTime: '',
  endTime: '',
  estimatedMinutes: '',
  projectId: '',
})
const validationError = ref<string | null>(null)

function submit(): void {
  const title = form.title.trim()
  if (!title) {
    validationError.value = '请输入任务标题'
    return
  }
  if (form.startTime && form.endTime && form.endTime <= form.startTime) {
    validationError.value = '结束时间必须晚于开始时间'
    return
  }
  const estimatedMinutes = form.estimatedMinutes ? Number(form.estimatedMinutes) : null
  if (estimatedMinutes !== null && (estimatedMinutes < 1 || estimatedMinutes > 1440)) {
    validationError.value = '预计时长需在 1 到 1440 分钟之间'
    return
  }
  validationError.value = null
  emit('submit', {
    title,
    description: form.description.trim() || null,
    priority: form.priority,
    scheduled_date: form.scheduledDate,
    start_time: form.startTime || null,
    end_time: form.endTime || null,
    estimated_minutes: estimatedMinutes,
    project_id: form.projectId ? Number(form.projectId) : null,
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        任务标题
        <input v-model="form.title" maxlength="160" autocomplete="off" placeholder="例如：完成项目接口联调" />
      </label>
      <label class="field field-span-2">
        任务说明
        <textarea v-model="form.description" maxlength="5000" placeholder="记录完成标准或需要注意的内容" />
      </label>
      <label class="field">
        日期
        <input v-model="form.scheduledDate" type="date" required />
      </label>
      <label class="field">
        优先级
        <select v-model="form.priority">
          <option value="low">低优先级</option>
          <option value="medium">普通</option>
          <option value="high">高优先级</option>
        </select>
      </label>
      <label class="field">
        开始时间
        <input v-model="form.startTime" type="time" />
      </label>
      <label class="field">
        结束时间
        <input v-model="form.endTime" type="time" />
      </label>
      <label class="field">
        预计时长（分钟）
        <input v-model="form.estimatedMinutes" type="number" min="1" max="1440" placeholder="60" />
      </label>
      <label class="field">
        关联项目
        <select v-model="form.projectId">
          <option value="">不关联项目</option>
          <option v-for="project in projects" :key="project.id" :value="String(project.id)">
            {{ project.name }}
          </option>
        </select>
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">
        {{ submitting ? '创建中…' : '创建任务' }}
      </button>
    </div>
  </form>
</template>
