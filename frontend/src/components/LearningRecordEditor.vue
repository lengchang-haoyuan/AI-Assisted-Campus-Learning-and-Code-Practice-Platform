<script setup lang="ts">
import { reactive, ref } from 'vue'

import { toLocalDateTimeInput } from '@/domain/learning'
import type { ProjectResponse } from '@/types/project'
import type {
  CourseResponse,
  LearningRecordCreateInput,
  LearningRecordResponse,
  LearningTaskResponse,
} from '@/types/learning'
import type { RecordType } from '@/types/workspace'

const props = defineProps<{
  initialValue: LearningRecordResponse | null
  courses: CourseResponse[]
  projects: ProjectResponse[]
  tasks: LearningTaskResponse[]
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: LearningRecordCreateInput]
  cancel: []
}>()

const now = new Date()
const form = reactive({
  title: props.initialValue?.title ?? '',
  content: props.initialValue?.content ?? '',
  recordType: (props.initialValue?.record_type ?? 'study') as RecordType,
  durationMinutes: props.initialValue ? String(props.initialValue.duration_minutes) : '',
  occurredAt: props.initialValue
    ? toLocalDateTimeInput(props.initialValue.occurred_at)
    : toLocalDateTimeInput(now.toISOString()),
  projectId: props.initialValue?.project ? String(props.initialValue.project.id) : '',
  courseId: props.initialValue?.course ? String(props.initialValue.course.id) : '',
  taskId: props.initialValue?.task ? String(props.initialValue.task.id) : '',
})
const validationError = ref<string | null>(null)

function submit(): void {
  const title = form.title.trim()
  const durationMinutes = Number(form.durationMinutes)
  if (!title) {
    validationError.value = '请输入记录标题'
    return
  }
  if (!Number.isInteger(durationMinutes) || durationMinutes < 1 || durationMinutes > 1440) {
    validationError.value = '学习时长需在 1 到 1440 分钟之间'
    return
  }
  if (form.recordType === 'project' && !form.projectId) {
    validationError.value = '项目实践记录必须关联项目'
    return
  }
  if (form.recordType === 'course' && !form.courseId) {
    validationError.value = '课程学习记录必须关联课程'
    return
  }
  if (form.recordType === 'task' && !form.taskId) {
    validationError.value = '任务复盘记录必须关联任务'
    return
  }
  validationError.value = null
  emit('submit', {
    title,
    content: form.content.trim() || null,
    record_type: form.recordType,
    duration_minutes: durationMinutes,
    occurred_at: new Date(form.occurredAt).toISOString(),
    project_id: form.projectId ? Number(form.projectId) : null,
    course_id: form.courseId ? Number(form.courseId) : null,
    task_id: form.taskId ? Number(form.taskId) : null,
    record_metadata: null,
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        记录标题
        <input v-model="form.title" maxlength="160" autocomplete="off" placeholder="例如：完成软件工程课程任务" />
      </label>
      <label class="field">
        记录类型
        <select v-model="form.recordType">
          <option value="study">自主学习</option><option value="project">项目实践</option><option value="workflow">工作流</option>
          <option value="ai">AI 辅助</option><option value="course">课程学习</option><option value="task">任务复盘</option>
        </select>
      </label>
      <label class="field">
        学习时长（分钟）
        <input v-model="form.durationMinutes" type="number" min="1" max="1440" required />
      </label>
      <label class="field">
        发生时间
        <input v-model="form.occurredAt" type="datetime-local" required />
      </label>
      <label class="field">
        关联课程
        <select v-model="form.courseId">
          <option value="">不关联课程</option>
          <option v-for="course in courses" :key="course.id" :value="String(course.id)">{{ course.name }}</option>
        </select>
      </label>
      <label class="field">
        关联项目
        <select v-model="form.projectId">
          <option value="">不关联项目</option>
          <option v-for="project in projects" :key="project.id" :value="String(project.id)">{{ project.name }}</option>
        </select>
      </label>
      <label class="field">
        关联任务
        <select v-model="form.taskId">
          <option value="">不关联任务</option>
          <option v-for="task in tasks" :key="task.id" :value="String(task.id)">{{ task.title }}</option>
        </select>
      </label>
      <label class="field field-span-2">
        学习内容
        <textarea v-model="form.content" maxlength="10000" placeholder="记录学习内容、产出和遇到的问题" />
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">{{ submitting ? '保存中…' : '保存记录' }}</button>
    </div>
  </form>
</template>
