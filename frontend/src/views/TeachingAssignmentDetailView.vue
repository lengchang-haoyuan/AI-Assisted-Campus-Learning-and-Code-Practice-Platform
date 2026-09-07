<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import {
  archiveTeachingAssignment,
  closeTeachingAssignment,
  getTeachingAssignment,
  publishTeachingAssignment,
  updateTeachingAssignment,
} from '@/api/teaching'
import type { TeachingAssignmentResponse } from '@/types/teaching'

const route = useRoute()
const assignmentId = Number(route.params.assignmentId)
const assignment = ref<TeachingAssignmentResponse | null>(null)
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const editing = ref(false)
const title = ref('')
const instructions = ref('')
const objectives = ref('')
const criteria = ref('')
const dueAt = ref('')

const isDraft = computed(() => assignment.value?.status === 'draft')

function formatDate(value: string | null): string {
  if (!value) return '未设置'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(value))
}

function toLocalDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

function fillForm(value: TeachingAssignmentResponse): void {
  title.value = value.title
  instructions.value = value.instructions
  objectives.value = value.learning_objectives.join('\n')
  criteria.value = value.acceptance_criteria.join('\n')
  dueAt.value = toLocalDateTime(value.due_at)
}

async function loadAssignment(): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const value = await getTeachingAssignment(assignmentId)
    assignment.value = value
    fillForm(value)
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '任务详情加载失败')
  } finally { loading.value = false }
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

async function saveAssignment(): Promise<void> {
  if (!assignment.value || saving.value || !dueAt.value) return
  saving.value = true
  try {
    const input = isDraft.value
      ? {
          expected_revision: assignment.value.revision,
          title: title.value.trim(),
          instructions: instructions.value.trim(),
          learning_objectives: lines(objectives.value),
          acceptance_criteria: lines(criteria.value),
          due_at: new Date(dueAt.value).toISOString(),
        }
      : { expected_revision: assignment.value.revision, due_at: new Date(dueAt.value).toISOString() }
    assignment.value = await updateTeachingAssignment(assignmentId, input)
    fillForm(assignment.value)
    editing.value = false
    ElMessage.success(isDraft.value ? '任务草稿已更新' : '截止时间已延长')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务保存失败'))
  } finally { saving.value = false }
}

async function transition(action: 'publish' | 'close' | 'archive'): Promise<void> {
  if (!assignment.value || saving.value) return
  const labels = { publish: '发布', close: '关闭', archive: '归档' }
  try {
    await ElMessageBox.confirm(`确定${labels[action]}这个教学任务吗？`, `${labels[action]}任务`, { type: action === 'publish' ? 'info' : 'warning' })
    saving.value = true
    const handlers = { publish: publishTeachingAssignment, close: closeTeachingAssignment, archive: archiveTeachingAssignment }
    assignment.value = await handlers[action](assignmentId, assignment.value.revision)
    fillForm(assignment.value)
    editing.value = false
    ElMessage.success(`任务已${labels[action]}`)
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, `任务${labels[action]}失败`))
  } finally { saving.value = false }
}

onMounted(() => void loadAssignment())
</script>

<template>
  <div class="page-shell teaching-page">
    <RouterLink v-if="assignment" class="back-link" :to="`/campus/classes/${assignment.class_id}`">← 返回班级</RouterLink>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadAssignment">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading"><span v-for="index in 3" :key="index" /></div>
    <article v-else-if="assignment" class="assignment-detail">
      <header class="assignment-detail__header">
        <div><span class="status-chip">{{ { draft: '草稿', published: '已发布', closed: '已关闭', archived: '已归档' }[assignment.status] }}</span><h1>{{ assignment.title }}</h1><p>修订 v{{ assignment.revision }} · 更新于 {{ formatDate(assignment.updated_at) }}</p></div>
        <div class="form-actions">
          <button v-if="assignment.can_edit" class="secondary-command" type="button" @click="editing = !editing">{{ editing ? '取消编辑' : assignment.status === 'draft' ? '编辑草稿' : '延长截止时间' }}</button>
          <button v-if="assignment.can_publish" class="primary-command" type="button" :disabled="saving" @click="transition('publish')">发布任务</button>
          <button v-if="assignment.can_close" class="danger-command" type="button" :disabled="saving" @click="transition('close')">关闭任务</button>
          <button v-if="assignment.can_archive" class="danger-command" type="button" :disabled="saving" @click="transition('archive')">归档任务</button>
        </div>
      </header>

      <form v-if="editing" class="teaching-panel form-grid" @submit.prevent="saveAssignment">
        <label v-if="isDraft" class="field field-span-2"><span>任务标题</span><input v-model.trim="title" required minlength="2" maxlength="160" /></label>
        <label v-if="isDraft" class="field field-span-2"><span>任务说明</span><textarea v-model.trim="instructions" required minlength="10" maxlength="20000" /></label>
        <label v-if="isDraft" class="field"><span>学习目标（每行一项）</span><textarea v-model="objectives" required /></label>
        <label v-if="isDraft" class="field"><span>交付要求（每行一项）</span><textarea v-model="criteria" required /></label>
        <label class="field"><span>截止时间（本地时区）</span><input v-model="dueAt" type="datetime-local" required /></label>
        <div class="form-actions field-span-2"><button class="primary-command" type="submit" :disabled="saving">{{ saving ? '正在保存' : '保存修改' }}</button></div>
      </form>

      <div class="assignment-detail__grid">
        <section class="teaching-panel assignment-copy"><span>任务说明</span><p>{{ assignment.instructions }}</p></section>
        <aside class="teaching-panel assignment-deadline"><span>截止时间</span><strong>{{ formatDate(assignment.due_at) }}</strong><small>页面按设备本地时区显示，数据库统一保存 UTC。</small></aside>
        <section class="teaching-panel"><span>学习目标</span><ol><li v-for="item in assignment.learning_objectives" :key="item">{{ item }}</li></ol></section>
        <section class="teaching-panel"><span>交付要求</span><ol><li v-for="item in assignment.acceptance_criteria" :key="item">{{ item }}</li></ol></section>
        <section v-if="assignment.source_project_snapshot" class="teaching-panel field-span-2 assignment-snapshot">
          <span>项目模板快照</span><h2>{{ assignment.source_project_snapshot.name }}</h2><p>{{ assignment.source_project_snapshot.description || '未填写项目说明。' }}</p><small>快照采集于 {{ formatDate(String(assignment.source_project_snapshot.captured_at)) }}；源项目后续修改不会改变本任务。</small>
        </section>
      </div>
    </article>
  </div>
</template>
