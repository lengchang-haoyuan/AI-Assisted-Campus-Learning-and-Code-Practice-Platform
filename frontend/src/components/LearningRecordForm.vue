<script setup lang="ts">
import { reactive, ref } from 'vue'

import type { ProjectResponse } from '@/types/project'
import type { LearningRecordCreateInput, RecordType } from '@/types/workspace'

defineProps<{
  projects: ProjectResponse[]
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: LearningRecordCreateInput]
  cancel: []
}>()

const form = reactive({
  title: '',
  content: '',
  recordType: 'study' as RecordType,
  durationMinutes: '30',
  projectId: '',
  occurredAt: '',
})
const validationError = ref<string | null>(null)

function submit(): void {
  const title = form.title.trim()
  const durationMinutes = Number(form.durationMinutes)
  if (!title) {
    validationError.value = '请输入学习记录标题'
    return
  }
  if (!Number.isInteger(durationMinutes) || durationMinutes < 1 || durationMinutes > 1440) {
    validationError.value = '学习时长需为 1 到 1440 之间的整数'
    return
  }
  if (form.recordType === 'project' && !form.projectId) {
    validationError.value = '项目实践记录必须关联项目'
    return
  }
  const parsedTime = form.occurredAt ? new Date(form.occurredAt) : null
  if (parsedTime && Number.isNaN(parsedTime.getTime())) {
    validationError.value = '记录时间格式不正确'
    return
  }
  validationError.value = null
  emit('submit', {
    title,
    content: form.content.trim() || null,
    record_type: form.recordType,
    duration_minutes: durationMinutes,
    project_id: form.projectId ? Number(form.projectId) : null,
    occurred_at: parsedTime?.toISOString() ?? null,
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        记录标题
        <input v-model="form.title" maxlength="160" autocomplete="off" placeholder="例如：复习 SQLAlchemy 聚合查询" />
      </label>
      <label class="field field-span-2">
        学习内容
        <textarea v-model="form.content" maxlength="10000" placeholder="写下完成的内容、理解或问题" />
      </label>
      <label class="field">
        记录类型
        <select v-model="form.recordType">
          <option value="study">自主学习</option>
          <option value="project">项目实践</option>
        </select>
        <span class="muted-copy">
          课程学习和任务复盘请前往
          <RouterLink to="/learning/records">学习系统的记录页面</RouterLink>，关联来源后创建。
        </span>
      </label>
      <label class="field">
        学习时长（分钟）
        <input v-model="form.durationMinutes" type="number" min="1" max="1440" required />
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
      <label class="field">
        发生时间
        <input v-model="form.occurredAt" type="datetime-local" />
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">
        {{ submitting ? '保存中…' : '保存记录' }}
      </button>
    </div>
  </form>
</template>
