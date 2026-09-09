<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { listProjects } from '@/api/projects'
import { listAssignmentSubmissions, submitAssignment } from '@/api/submissions'
import {
  archiveTeachingAssignment,
  closeTeachingAssignment,
  getTeachingAssignment,
  publishTeachingAssignment,
  updateTeachingAssignment,
} from '@/api/teaching'
import type { TeachingAssignmentResponse } from '@/types/teaching'
import type { ProjectResponse } from '@/types/project'
import type { SubmissionResponse } from '@/types/submission'

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
const campusRole = ref<'student' | 'teacher' | 'administrator' | null>(null)
const submissions = ref<SubmissionResponse[]>([])
const projects = ref<ProjectResponse[]>([])
const submissionSummary = ref('')
const repositoryUrl = ref('')
const repositoryRef = ref('')
const sourceProjectId = ref<number | null>(null)
const requestKey = ref(crypto.randomUUID().replaceAll('-', ''))

const isDraft = computed(() => assignment.value?.status === 'draft')
const ownSubmission = computed(() => submissions.value.find((item) => item.is_owner) ?? null)
const canSubmit = computed(() => {
  if (campusRole.value !== 'student' || assignment.value?.status !== 'published') return false
  if (!assignment.value.due_at || Date.now() >= new Date(assignment.value.due_at).getTime()) return false
  return !ownSubmission.value || ownSubmission.value.can_submit_next
})

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
    const [value, campus] = await Promise.all([getTeachingAssignment(assignmentId), getCampusMe()])
    assignment.value = value
    campusRole.value = campus.membership?.role ?? null
    fillForm(value)
    submissions.value = (await listAssignmentSubmissions(assignmentId)).items
    if (campusRole.value === 'student') {
      projects.value = (await listProjects({ page: 1, pageSize: 100 })).items
    }
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '任务详情加载失败')
  } finally { loading.value = false }
}

async function submitWork(): Promise<void> {
  if (!assignment.value || !canSubmit.value || saving.value) return
  saving.value = true
  try {
    await submitAssignment(assignmentId, {
      request_key: requestKey.value,
      expected_latest_version: ownSubmission.value?.latest_version_number ?? 0,
      summary: submissionSummary.value.trim(),
      repository_url: repositoryUrl.value.trim() || null,
      repository_ref: repositoryRef.value.trim() || null,
      source_project_id: sourceProjectId.value,
    })
    submissions.value = (await listAssignmentSubmissions(assignmentId)).items
    submissionSummary.value = ''
    repositoryUrl.value = ''
    repositoryRef.value = ''
    sourceProjectId.value = null
    requestKey.value = crypto.randomUUID().replaceAll('-', '')
    ElMessage.success(ownSubmission.value?.latest_version_number === 1 ? '成果已提交' : '新版本已提交')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '成果提交失败'))
  } finally { saving.value = false }
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

      <section v-if="campusRole === 'student'" class="teaching-panel submission-panel">
        <div class="teaching-panel__heading">
          <div><span>我的成果</span><h2>{{ ownSubmission ? `当前为 V${ownSubmission.latest_version_number}` : '提交第一版成果' }}</h2></div>
          <RouterLink v-if="ownSubmission" class="secondary-command" :to="`/campus/submissions/${ownSubmission.id}`">查看版本与反馈</RouterLink>
        </div>
        <div v-if="ownSubmission" class="submission-current">
          <span class="status-chip">{{ { submitted: '待教师评阅', returned: '已退回修改', accepted: '已通过' }[ownSubmission.latest_version.status] }}</span>
          <p>{{ ownSubmission.latest_version.summary }}</p>
          <small v-if="ownSubmission.latest_version.feedback">教师意见：{{ ownSubmission.latest_version.feedback.comment }}</small>
        </div>
        <form v-if="canSubmit" class="form-grid submission-form" @submit.prevent="submitWork">
          <label class="field field-span-2"><span>成果说明</span><textarea v-model="submissionSummary" required minlength="1" maxlength="8000" placeholder="说明完成内容、运行方法和已知问题" /></label>
          <label class="field"><span>仓库链接（可选）</span><input v-model.trim="repositoryUrl" type="url" maxlength="1024" placeholder="https://github.com/user/repository" /></label>
          <label class="field"><span>代码版本（可选）</span><input v-model.trim="repositoryRef" maxlength="100" placeholder="main、标签或提交标识" /></label>
          <label class="field field-span-2"><span>关联本人项目（可选）</span><select v-model="sourceProjectId"><option :value="null">不关联</option><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label>
          <div class="form-actions field-span-2"><button class="primary-command" type="submit" :disabled="saving">{{ saving ? '正在提交' : ownSubmission ? '提交新版本' : '提交成果' }}</button></div>
        </form>
        <div v-else-if="!ownSubmission" class="teaching-note">任务尚未发布、已截止或当前不可提交。</div>
      </section>

      <section v-else-if="campusRole === 'teacher'" class="teaching-panel submission-panel">
        <div class="teaching-panel__heading"><div><span>学生成果</span><h2>提交与待评阅</h2></div><RouterLink class="secondary-command" to="/campus/submissions">打开待处理列表</RouterLink></div>
        <div v-if="submissions.length" class="submission-list">
          <RouterLink v-for="item in submissions" :key="item.id" :to="`/campus/submissions/${item.id}`">
            <div><strong>{{ item.student_username }} · V{{ item.latest_version_number }}</strong><p>{{ item.latest_version.summary }}</p></div>
            <span class="status-chip">{{ { submitted: '待评阅', returned: '已退回', accepted: '已通过' }[item.latest_version.status] }}</span>
          </RouterLink>
        </div>
        <div v-else class="teaching-note">还没有学生提交成果。</div>
      </section>
    </article>
  </div>
</template>
