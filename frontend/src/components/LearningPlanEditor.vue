<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import type { JsonValue, ProjectResponse } from '@/types/project'
import type {
  CourseResponse,
  LearningPlanCreateInput,
  LearningPlanResponse,
  LearningPlanStatus,
} from '@/types/learning'

const props = defineProps<{
  initialValue: LearningPlanResponse | null
  courses: CourseResponse[]
  projects: ProjectResponse[]
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: LearningPlanCreateInput]
  cancel: []
}>()

function structuredText(value: Record<string, JsonValue> | null): string {
  return typeof value?.text === 'string' ? value.text : ''
}

const form = reactive({
  title: props.initialValue?.title ?? '',
  description: props.initialValue?.description ?? '',
  status: (props.initialValue?.status ?? 'draft') as LearningPlanStatus,
  startDate: props.initialValue?.start_date ?? '',
  endDate: props.initialValue?.end_date ?? '',
  goalText: structuredText(props.initialValue?.goal_data ?? null),
  projectId: props.initialValue?.project ? String(props.initialValue.project.id) : '',
  courseId: props.initialValue?.course ? String(props.initialValue.course.id) : '',
})
const validationError = ref<string | null>(null)

const statusOptions = computed<Array<{ value: LearningPlanStatus; label: string }>>(() => {
  const current = props.initialValue?.status
  if (current === 'completed') return [{ value: 'completed', label: '已完成' }]
  if (current === 'cancelled') return [{ value: 'cancelled', label: '已取消' }]
  if (current === 'active') {
    return [
      { value: 'active', label: '进行中' },
      { value: 'completed', label: '已完成' },
      { value: 'cancelled', label: '已取消' },
    ]
  }
  return [
    { value: 'draft', label: '草稿' },
    { value: 'active', label: '进行中' },
    { value: 'cancelled', label: '已取消' },
  ]
})

function submit(): void {
  const title = form.title.trim()
  if (!title) {
    validationError.value = '请输入计划标题'
    return
  }
  if (form.startDate && form.endDate && form.endDate < form.startDate) {
    validationError.value = '计划结束日期不能早于开始日期'
    return
  }
  validationError.value = null
  emit('submit', {
    title,
    description: form.description.trim() || null,
    status: form.status,
    start_date: form.startDate || null,
    end_date: form.endDate || null,
    goal_data: form.goalText.trim() ? { text: form.goalText.trim() } : null,
    project_id: form.projectId ? Number(form.projectId) : null,
    course_id: form.courseId ? Number(form.courseId) : null,
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        计划标题
        <input v-model="form.title" maxlength="160" autocomplete="off" placeholder="例如：四周完成课程项目" />
      </label>
      <label class="field">
        开始日期
        <input v-model="form.startDate" type="date" />
      </label>
      <label class="field">
        结束日期
        <input v-model="form.endDate" type="date" />
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
        状态
        <select v-model="form.status">
          <option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label class="field">
        目标摘要
        <input v-model="form.goalText" maxlength="5000" autocomplete="off" placeholder="定义可验收的学习目标" />
      </label>
      <label class="field field-span-2">
        计划说明
        <textarea v-model="form.description" maxlength="5000" placeholder="说明学习范围、节奏与完成标准" />
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">
        {{ submitting ? '保存中…' : initialValue ? '保存计划' : '创建计划' }}
      </button>
    </div>
  </form>
</template>
