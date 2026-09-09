<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { listPendingAssignments, listSubmissions } from '@/api/submissions'
import type { PendingAssignmentResponse, SubmissionResponse } from '@/types/submission'

const role = ref<'student' | 'teacher' | 'administrator' | null>(null)
const items = ref<SubmissionResponse[]>([])
const pendingAssignments = ref<PendingAssignmentResponse[]>([])
const loading = ref(true)
const errorMessage = ref<string | null>(null)
const pendingOnly = ref(true)
const page = ref(1)
const totalPages = ref(0)
const pendingPage = ref(1)
const pendingTotalPages = ref(0)

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function loadPage(targetPage = page.value, targetPendingPage = pendingPage.value): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const membership = (await getCampusMe()).membership
    role.value = membership?.role ?? null
    if (role.value === 'student') {
      const [submissionPage, pendingResult] = await Promise.all([
        listSubmissions(targetPage),
        listPendingAssignments(targetPendingPage),
      ])
      items.value = submissionPage.items
      pendingAssignments.value = pendingResult.items
      page.value = submissionPage.page
      totalPages.value = submissionPage.total_pages
      pendingPage.value = pendingResult.page
      pendingTotalPages.value = pendingResult.total_pages
    } else {
      const result = await listSubmissions(targetPage, role.value === 'teacher' && pendingOnly.value)
      items.value = result.items
      page.value = result.page
      totalPages.value = result.total_pages
      pendingAssignments.value = []
      pendingPage.value = 1
      pendingTotalPages.value = 0
    }
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '提交列表加载失败')
  } finally { loading.value = false }
}

onMounted(() => void loadPage())
</script>

<template>
  <div class="page-shell teaching-page">
    <header class="page-header teaching-header">
      <div><p class="page-kicker">教学闭环</p><h1>{{ role === 'teacher' ? '学生成果' : '我的提交' }}</h1><p>{{ role === 'teacher' ? '评阅当前班级待处理的最新版本。' : '查看所有提交版本和教师反馈。' }}</p></div>
      <label v-if="role === 'teacher'" class="submission-filter"><input v-model="pendingOnly" type="checkbox" @change="loadPage(1, 1)" /> 只看待评阅</label>
    </header>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadPage()">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading"><span v-for="index in 3" :key="index" /></div>
    <section v-else-if="role === 'student' && pendingAssignments.length" class="teaching-panel pending-assignment-panel">
      <div class="teaching-panel__heading"><div><span>需要处理</span><h2>待提交与待修改</h2></div><p>只显示截止前仍可操作的任务。</p></div>
      <div class="submission-list">
        <RouterLink v-for="assignment in pendingAssignments" :key="assignment.id" :to="`/campus/assignments/${assignment.id}`">
          <div><strong>{{ assignment.title }}</strong><p>截止：{{ formatDate(assignment.due_at) }}</p></div>
          <span class="status-chip">{{ assignment.current_status === 'returned' ? '修改后重交' : '首次提交' }}</span>
        </RouterLink>
      </div>
      <nav v-if="pendingTotalPages > 1" class="teaching-pagination" aria-label="待处理任务分页">
        <button class="secondary-command compact-command" type="button" :disabled="pendingPage <= 1 || loading" @click="loadPage(page, pendingPage - 1)">上一页</button>
        <span>第 {{ pendingPage }} / {{ pendingTotalPages }} 页</span>
        <button class="secondary-command compact-command" type="button" :disabled="pendingPage >= pendingTotalPages || loading" @click="loadPage(page, pendingPage + 1)">下一页</button>
      </nav>
    </section>
    <div v-else-if="role === 'student' && !loading" class="teaching-note pending-assignment-empty">当前没有待提交或待修改任务。</div>
    <section v-if="!loading && items.length" class="submission-card-grid" aria-label="成果提交列表">
      <RouterLink v-for="item in items" :key="item.id" :to="`/campus/submissions/${item.id}`" class="teaching-panel submission-card">
        <div class="teaching-card-topline"><span class="status-chip">{{ { submitted: '待评阅', returned: '已退回', accepted: '已通过' }[item.latest_version.status] }}</span><small>V{{ item.latest_version_number }}</small></div>
        <h2>{{ item.assignment_title }}</h2>
        <p>{{ role === 'teacher' ? `提交者：${item.student_username}` : item.latest_version.summary }}</p>
        <footer><span>提交于 {{ formatDate(item.latest_version.submitted_at) }}</span><strong>查看详情 →</strong></footer>
      </RouterLink>
    </section>
    <div v-else-if="!loading && role !== 'student'" class="teaching-note">{{ role === 'teacher' && pendingOnly ? '当前没有待评阅成果。' : '还没有成果提交记录。' }}</div>
    <nav v-if="!loading && totalPages > 1" class="teaching-pagination" aria-label="成果提交分页">
      <button class="secondary-command compact-command" type="button" :disabled="page <= 1" @click="loadPage(page - 1, pendingPage)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button class="secondary-command compact-command" type="button" :disabled="page >= totalPages" @click="loadPage(page + 1, pendingPage)">下一页</button>
    </nav>
  </div>
</template>
