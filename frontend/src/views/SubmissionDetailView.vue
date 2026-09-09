<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { createFeedback, detachProjectReference, getSubmission, listSubmissionVersions } from '@/api/submissions'
import type { FeedbackDecision, SubmissionResponse, SubmissionVersionResponse } from '@/types/submission'

const route = useRoute()
const submissionId = Number(route.params.submissionId)
const submission = ref<SubmissionResponse | null>(null)
const versions = ref<SubmissionVersionResponse[]>([])
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const comment = ref('')
const page = ref(1)
const totalPages = ref(0)

const latest = computed(() => versions.value.find((item) => item.version_number === submission.value?.latest_version_number) ?? null)

function formatDate(value: string | null): string {
  if (!value) return '未记录'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function loadPage(targetPage = page.value): Promise<void> {
  if (!Number.isInteger(submissionId) || submissionId < 1) {
    errorMessage.value = '提交地址无效'
    loading.value = false
    return
  }
  loading.value = true
  errorMessage.value = null
  try {
    const [detail, history] = await Promise.all([getSubmission(submissionId), listSubmissionVersions(submissionId, targetPage)])
    submission.value = detail
    versions.value = history.items
    page.value = history.page
    totalPages.value = history.total_pages
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '提交详情加载失败')
  } finally { loading.value = false }
}

async function review(decision: FeedbackDecision): Promise<void> {
  if (!submission.value || !latest.value || saving.value || !comment.value.trim()) return
  const label = decision === 'accept' ? '确认通过' : '退回修改'
  try {
    await ElMessageBox.confirm(`评阅结论会固定到 V${latest.value.version_number}，确定${label}吗？`, label, { type: decision === 'accept' ? 'success' : 'warning' })
    saving.value = true
    await createFeedback(submissionId, latest.value.version_number, submission.value.revision, decision, comment.value.trim())
    comment.value = ''
    await loadPage()
    ElMessage.success(`已${label}`)
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '评阅失败'))
  } finally { saving.value = false }
}

async function detach(version: SubmissionVersionResponse): Promise<void> {
  if (saving.value) return
  try {
    await ElMessageBox.confirm('仅解除与私人项目的来源关联，已提交文字和项目标题快照仍会保留。', '解除项目关联', { type: 'warning' })
    saving.value = true
    await detachProjectReference(submissionId, version.version_number)
    await loadPage()
    ElMessage.success('已解除项目来源关联')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '解除关联失败'))
  } finally { saving.value = false }
}

onMounted(() => void loadPage())
</script>

<template>
  <div class="page-shell teaching-page">
    <RouterLink v-if="submission" class="back-link" :to="`/campus/assignments/${submission.assignment_id}`">← 返回教学任务</RouterLink>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadPage()">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading"><span v-for="index in 3" :key="index" /></div>
    <template v-else-if="submission">
      <header class="teaching-detail-hero">
        <div><p class="page-kicker">{{ submission.student_username }} · 最新 V{{ submission.latest_version_number }}</p><h1>{{ submission.assignment_title }}</h1><p>首次提交时截止：{{ formatDate(submission.assignment_due_at) }}</p></div>
        <span class="status-chip">{{ { submitted: '待评阅', returned: '已退回', accepted: '已通过' }[submission.latest_version.status] }}</span>
      </header>

      <section v-if="submission.can_review && latest" class="teaching-panel feedback-form">
        <div class="teaching-panel__heading"><div><span>教师评阅</span><h2>评阅 V{{ latest.version_number }}</h2></div><p>结论与意见将固定到当前版本，不能覆盖历史。</p></div>
        <label class="field"><span>反馈意见</span><textarea v-model="comment" required minlength="1" maxlength="4000" placeholder="说明通过依据或需要修改的内容" /></label>
        <div class="form-actions"><button class="danger-command" type="button" :disabled="saving || !comment.trim()" @click="review('return')">退回修改</button><button class="primary-command" type="button" :disabled="saving || !comment.trim()" @click="review('accept')">确认通过</button></div>
      </section>

      <section class="submission-history" aria-labelledby="history-title">
        <div class="teaching-panel__heading"><div><span>不可覆盖历史</span><h2 id="history-title">版本与反馈</h2></div></div>
        <article v-for="version in versions" :key="version.id" class="teaching-panel submission-version">
          <header><div><span class="status-chip">V{{ version.version_number }} · {{ { submitted: '待评阅', returned: '已退回', accepted: '已通过' }[version.status] }}</span><small>{{ formatDate(version.submitted_at) }}</small></div><button v-if="submission.is_owner && version.has_project_reference" class="text-command danger-text-command" type="button" :disabled="saving" @click="detach(version)">解除项目关联</button></header>
          <p>{{ version.summary }}</p>
          <dl v-if="version.repository_url || version.repository_ref || version.source_project_title">
            <div v-if="version.repository_url"><dt>仓库</dt><dd><a :href="version.repository_url" target="_blank" rel="noopener noreferrer">{{ version.repository_url }}</a></dd></div>
            <div v-if="version.repository_ref"><dt>版本标识</dt><dd>{{ version.repository_ref }}</dd></div>
            <div v-if="version.source_project_title"><dt>项目标题快照</dt><dd>{{ version.source_project_title }}</dd></div>
          </dl>
          <aside v-if="version.feedback" class="feedback-result"><strong>{{ version.feedback.decision === 'accept' ? '教师确认通过' : '教师退回修改' }}</strong><p>{{ version.feedback.comment }}</p><small>{{ formatDate(version.feedback.created_at) }}</small></aside>
        </article>
        <nav v-if="totalPages > 1" class="teaching-pagination" aria-label="提交版本分页">
          <button class="secondary-command compact-command" type="button" :disabled="page <= 1 || loading" @click="loadPage(page - 1)">上一页</button>
          <span>第 {{ page }} / {{ totalPages }} 页</span>
          <button class="secondary-command compact-command" type="button" :disabled="page >= totalPages || loading" @click="loadPage(page + 1)">下一页</button>
        </nav>
      </section>
    </template>
  </div>
</template>
