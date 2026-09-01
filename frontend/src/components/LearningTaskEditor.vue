<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { getLocalDateValue } from '@/domain/workspace'
import type { ProjectResponse } from '@/types/project'
import type {
  LearningPlanResponse,
  LearningTaskCreateInput,
  LearningTaskResponse,
} from '@/types/learning'
import type { TaskPriority, TaskStatus } from '@/types/workspace'

const props = defineProps<{
  initialValue: LearningTaskResponse | null
  plans: LearningPlanResponse[]
  projects: ProjectResponse[]
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: LearningTaskCreateInput & { status?: TaskStatus }]
  cancel: []
}>()

const form = reactive({
  title: props.initialValue?.title ?? '',
  description: props.initialValue?.description ?? '',
  priority: (props.initialValue?.priority ?? 'medium') as TaskPriority,
  status: (props.initialValue?.status ?? 'pending') as TaskStatus,
  scheduledDate: props.initialValue?.scheduled_date ?? getLocalDateValue(),
  startTime: props.initialValue?.start_time?.slice(0, 5) ?? '',
  endTime: props.initialValue?.end_time?.slice(0, 5) ?? '',
  estimatedMinutes: props.initialValue?.estimated_minutes
    ? String(props.initialValue.estimated_minutes)
    : '',
  planId: props.initialValue?.plan ? String(props.initialValue.plan.id) : '',
  projectId: props.initialValue?.project ? String(props.initialValue.project.id) : '',
})
const validationError = ref<string | null>(null)

const canChangeStatus = computed(() => {
  const status = props.initialValue?.status
  return status !== 'completed' && status !== 'cancelled'
})

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
    plan_id: form.planId ? Number(form.planId) : null,
    project_id: form.projectId ? Number(form.projectId) : null,
    ...(props.initialValue && canChangeStatus.value ? { status: form.status } : {}),
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        任务标题
        <input v-model="form.title" maxlength="160" autocomplete="off" placeholder="例如：完成课程项目数据库设计" />
      </label>
      <label class="field">
        日期
        <input v-model="form.scheduledDate" type="date" required />
      </label>
      <label class="field">
        优先级
        <select v-model="form.priority">
          <option value="low">低优先级</option><option value="medium">普通</option><option value="high">高优先级</option>
        </select>
      </label>
      <label v-if="initialValue" class="field">
        状态
        <select v-model="form.status" :disabled="!canChangeStatus">
          <option value="pending">待完成</option><option value="in_progress">进行中</option>
          <option v-if="initialValue.status !== 'completed'" value="cancelled">已取消</option>
          <option v-if="!canChangeStatus" :value="initialValue.status">{{ initialValue.status === 'completed' ? '已完成' : '已取消' }}</option>
        </select>
      </label>
      <label class="field">
        预计时长（分钟）
        <input v-model="form.estimatedMinutes" type="number" min="1" max="1440" placeholder="60" />
      </label>
      <label class="field">
        关联计划
        <select v-model="form.planId">
          <option value="">不关联计划</option>
          <option v-for="plan in plans" :key="plan.id" :value="String(plan.id)">{{ plan.title }}</option>
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
        开始时间
        <input v-model="form.startTime" type="time" />
      </label>
      <label class="field">
        结束时间
        <input v-model="form.endTime" type="time" />
      </label>
      <label class="field field-span-2">
        任务说明
        <textarea v-model="form.description" maxlength="5000" placeholder="记录完成标准或需要注意的内容" />
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">{{ submitting ? '保存中…' : initialValue ? '保存任务' : '创建任务' }}</button>
    </div>
  </form>
</template>
