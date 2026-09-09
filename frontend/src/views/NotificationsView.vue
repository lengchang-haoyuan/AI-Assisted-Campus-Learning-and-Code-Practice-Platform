<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { listNotifications, markNotificationRead } from '@/api/submissions'
import type { NotificationResponse } from '@/types/submission'

const items = ref<NotificationResponse[]>([])
const router = useRouter()
const unreadCount = ref(0)
const unreadOnly = ref(false)
const loading = ref(true)
const errorMessage = ref<string | null>(null)
const page = ref(1)
const totalPages = ref(0)

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

async function loadPage(targetPage = page.value): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const result = await listNotifications(targetPage, unreadOnly.value)
    items.value = result.items
    unreadCount.value = result.unread_count
    page.value = result.page
    totalPages.value = result.total_pages
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '通知加载失败')
  } finally { loading.value = false }
}

async function openNotification(item: NotificationResponse): Promise<void> {
  try {
    if (!item.read_at) {
      item.read_at = (await markNotificationRead(item.id)).read_at
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
    await router.push(item.submission_id ? `/campus/submissions/${item.submission_id}` : `/campus/assignments/${item.assignment_id}`)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '通知状态更新失败'))
  }
}

onMounted(() => void loadPage())
</script>

<template>
  <div class="page-shell teaching-page">
    <header class="page-header teaching-header"><div><p class="page-kicker">站内通知</p><h1>教学消息</h1><p>未读 {{ unreadCount }} 条。通知不复制提交正文。</p></div><label class="submission-filter"><input v-model="unreadOnly" type="checkbox" @change="loadPage(1)" /> 只看未读</label></header>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadPage()">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading"><span v-for="index in 3" :key="index" /></div>
    <section v-else-if="items.length" class="notification-list">
      <a v-for="item in items" :key="item.id" class="teaching-panel notification-item" :class="{ 'is-unread': !item.read_at }" :href="item.submission_id ? `/campus/submissions/${item.submission_id}` : `/campus/assignments/${item.assignment_id}`" @click.prevent="openNotification(item)">
        <div><span class="status-chip">{{ item.kind === 'assignment_published' ? '新任务' : '教师反馈' }}</span><h2>{{ item.kind === 'assignment_published' ? '教学任务已发布' : '你的成果收到反馈' }}</h2><p>{{ formatDate(item.created_at) }}</p></div><strong>{{ item.read_at ? '查看' : '查看并标为已读' }} →</strong>
      </a>
    </section>
    <div v-else-if="!loading" class="teaching-note">{{ unreadOnly ? '没有未读通知。' : '暂无教学通知。' }}</div>
    <nav v-if="!loading && totalPages > 1" class="teaching-pagination" aria-label="通知分页">
      <button class="secondary-command compact-command" type="button" :disabled="page <= 1" @click="loadPage(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button class="secondary-command compact-command" type="button" :disabled="page >= totalPages" @click="loadPage(page + 1)">下一页</button>
    </nav>
  </div>
</template>
