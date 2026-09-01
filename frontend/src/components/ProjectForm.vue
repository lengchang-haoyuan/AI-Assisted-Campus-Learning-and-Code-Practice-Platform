<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { difficultyLabels, formatRequirement, statusLabels } from '@/domain/projects'
import {
  PROJECT_DIFFICULTIES,
  PROJECT_STATUSES,
  type ProjectCreateInput,
  type ProjectResponse,
} from '@/types/project'

const props = withDefaults(
  defineProps<{
    initialValue?: ProjectResponse | null
    submitting?: boolean
    submitLabel?: string
  }>(),
  {
    initialValue: null,
    submitting: false,
    submitLabel: '保存项目',
  },
)

const emit = defineEmits<{
  submit: [value: ProjectCreateInput]
  cancel: []
}>()

interface ProjectFormState {
  name: string
  description: string
  difficulty: ProjectCreateInput['difficulty']
  language: string
  framework: string
  frontend: string
  backend: string
  database: string
  requirementsText: string
  outputRequirement: string
  status: ProjectCreateInput['status']
}

const form = reactive<ProjectFormState>({
  name: '',
  description: '',
  difficulty: 'beginner',
  language: '',
  framework: '',
  frontend: '',
  backend: '',
  database: '',
  requirementsText: '',
  outputRequirement: '',
  status: 'not_started',
})
const errors = ref<Record<string, string>>({})

watch(
  () => props.initialValue,
  (project) => {
    form.name = project?.name ?? ''
    form.description = project?.description ?? ''
    form.difficulty = project?.difficulty ?? 'beginner'
    form.language = project?.language ?? ''
    form.framework = project?.framework ?? ''
    form.frontend = project?.frontend ?? ''
    form.backend = project?.backend ?? ''
    form.database = project?.database ?? ''
    form.requirementsText = project?.requirements?.map(formatRequirement).join('\n') ?? ''
    form.outputRequirement = project?.output_requirement ?? ''
    form.status = project?.status ?? 'not_started'
    errors.value = {}
  },
  { immediate: true },
)

function optional(value: string): string | null {
  const normalized = value.trim()
  return normalized || null
}

function validate(): boolean {
  const nextErrors: Record<string, string> = {}
  const name = form.name.trim()
  if (!name) nextErrors.name = '请输入项目名称'
  else if (name.length > 120) nextErrors.name = '项目名称不能超过 120 个字符'
  if (form.description.length > 5000) nextErrors.description = '项目说明不能超过 5000 个字符'

  const shortFields: Array<[keyof ProjectFormState, string]> = [
    ['language', '语言'],
    ['framework', '框架'],
    ['frontend', '前端'],
    ['backend', '后端'],
    ['database', '数据库'],
  ]
  for (const [key, label] of shortFields) {
    if (form[key].length > 100) nextErrors[key] = `${label}不能超过 100 个字符`
  }
  if (form.outputRequirement.length > 10000) {
    nextErrors.outputRequirement = '交付要求不能超过 10000 个字符'
  }
  errors.value = nextErrors
  return Object.keys(nextErrors).length === 0
}

function submit(): void {
  if (!validate() || props.submitting) return
  const requirements = form.requirementsText
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((description) => ({ description }))

  emit('submit', {
    name: form.name.trim(),
    description: optional(form.description),
    difficulty: form.difficulty,
    language: optional(form.language),
    framework: optional(form.framework),
    frontend: optional(form.frontend),
    backend: optional(form.backend),
    database: optional(form.database),
    requirements: requirements.length > 0 ? requirements : null,
    output_requirement: optional(form.outputRequirement),
    status: form.status,
  })
}
</script>

<template>
  <form class="project-form" novalidate @submit.prevent="submit">
    <div class="form-grid">
      <label class="field field-span-2">
        <span>项目名称</span>
        <input v-model="form.name" maxlength="120" autocomplete="off" />
        <small v-if="errors.name" class="field-error">{{ errors.name }}</small>
      </label>

      <label class="field">
        <span>难度</span>
        <select v-model="form.difficulty">
          <option v-for="difficulty in PROJECT_DIFFICULTIES" :key="difficulty" :value="difficulty">
            {{ difficultyLabels[difficulty] }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>状态</span>
        <select v-model="form.status">
          <option v-for="status in PROJECT_STATUSES" :key="status" :value="status">
            {{ statusLabels[status] }}
          </option>
        </select>
      </label>

      <label class="field field-span-2">
        <span>项目说明</span>
        <textarea v-model="form.description" rows="4" maxlength="5000" />
        <small v-if="errors.description" class="field-error">{{ errors.description }}</small>
      </label>

      <label class="field">
        <span>主要语言</span>
        <input v-model="form.language" maxlength="100" autocomplete="off" />
        <small v-if="errors.language" class="field-error">{{ errors.language }}</small>
      </label>

      <label class="field">
        <span>核心框架</span>
        <input v-model="form.framework" maxlength="100" autocomplete="off" />
        <small v-if="errors.framework" class="field-error">{{ errors.framework }}</small>
      </label>

      <details class="advanced-fields field-span-2">
        <summary>完整技术与交付信息</summary>
        <div class="form-grid advanced-fields__content">
          <label class="field">
            <span>前端</span>
            <input v-model="form.frontend" maxlength="100" autocomplete="off" />
            <small v-if="errors.frontend" class="field-error">{{ errors.frontend }}</small>
          </label>
          <label class="field">
            <span>后端</span>
            <input v-model="form.backend" maxlength="100" autocomplete="off" />
            <small v-if="errors.backend" class="field-error">{{ errors.backend }}</small>
          </label>
          <label class="field field-span-2">
            <span>数据库</span>
            <input v-model="form.database" maxlength="100" autocomplete="off" />
            <small v-if="errors.database" class="field-error">{{ errors.database }}</small>
          </label>
          <label class="field field-span-2">
            <span>项目需求（每行一项）</span>
            <textarea v-model="form.requirementsText" rows="4" />
          </label>
          <label class="field field-span-2">
            <span>交付要求</span>
            <textarea v-model="form.outputRequirement" rows="4" maxlength="10000" />
            <small v-if="errors.outputRequirement" class="field-error">
              {{ errors.outputRequirement }}
            </small>
          </label>
        </div>
      </details>
    </div>

    <div class="form-actions">
      <button class="secondary-command" type="button" :disabled="submitting" @click="emit('cancel')">
        取消
      </button>
      <button class="primary-command" type="submit" :disabled="submitting">
        {{ submitting ? '正在保存…' : submitLabel }}
      </button>
    </div>
  </form>
</template>
