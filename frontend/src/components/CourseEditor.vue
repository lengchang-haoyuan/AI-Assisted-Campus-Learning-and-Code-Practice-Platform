<script setup lang="ts">
import { reactive, ref } from 'vue'

import type { JsonValue } from '@/types/project'
import type { CourseCreateInput, CourseResponse, CourseStatus } from '@/types/learning'

const props = defineProps<{
  initialValue: CourseResponse | null
  submitting: boolean
}>()

const emit = defineEmits<{
  submit: [input: CourseCreateInput]
  cancel: []
}>()

function structuredText(value: Record<string, JsonValue> | null): string {
  return typeof value?.text === 'string' ? value.text : ''
}

const form = reactive({
  name: props.initialValue?.name ?? '',
  code: props.initialValue?.code ?? '',
  description: props.initialValue?.description ?? '',
  instructor: props.initialValue?.instructor ?? '',
  scheduleText: structuredText(props.initialValue?.schedule_data ?? null),
  status: (props.initialValue?.status ?? 'active') as CourseStatus,
})
const validationError = ref<string | null>(null)

function submit(): void {
  const name = form.name.trim()
  if (!name) {
    validationError.value = '请输入课程名称'
    return
  }
  validationError.value = null
  emit('submit', {
    name,
    code: form.code.trim() || null,
    description: form.description.trim() || null,
    instructor: form.instructor.trim() || null,
    schedule_data: form.scheduleText.trim() ? { text: form.scheduleText.trim() } : null,
    status: form.status,
  })
}
</script>

<template>
  <form class="workspace-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="field">
        课程名称
        <input v-model="form.name" maxlength="120" autocomplete="off" placeholder="例如：软件工程" />
      </label>
      <label class="field">
        课程代码
        <input v-model="form.code" maxlength="50" autocomplete="off" placeholder="SE101" />
      </label>
      <label class="field">
        任课教师
        <input v-model="form.instructor" maxlength="100" autocomplete="off" placeholder="教师姓名" />
      </label>
      <label class="field">
        状态
        <select v-model="form.status">
          <option value="active">进行中</option>
          <option value="completed">已结课</option>
          <option value="archived">已归档</option>
        </select>
      </label>
      <label class="field field-span-2">
        课程说明
        <textarea v-model="form.description" maxlength="5000" placeholder="课程目标、内容或考核方式" />
      </label>
      <label class="field field-span-2">
        上课安排
        <textarea v-model="form.scheduleText" maxlength="5000" placeholder="例如：每周三 14:00，教学楼 A203" />
      </label>
    </div>
    <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
    <div class="form-actions workspace-form__actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">取消</button>
      <button class="primary-command" type="submit" :disabled="submitting">
        {{ submitting ? '保存中…' : initialValue ? '保存课程' : '创建课程' }}
      </button>
    </div>
  </form>
</template>
