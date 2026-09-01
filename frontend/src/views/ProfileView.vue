<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const createdAt = computed(() => {
  const value = authStore.currentUser?.created_at
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long' }).format(date)
})
const userInitial = computed(() => authStore.currentUser?.username.slice(0, 1).toUpperCase() || 'S')
</script>

<template>
  <div class="page-shell profile-page">
    <header class="page-header">
      <div><h1>个人资料</h1><p>查看当前登录账号的基础信息。</p></div>
    </header>

    <section v-if="authStore.currentUser" class="profile-board">
      <div class="profile-identity">
        <span class="avatar is-large" aria-hidden="true">{{ userInitial }}</span>
        <div>
          <h2>{{ authStore.currentUser.username }}</h2>
          <p>{{ authStore.currentUser.bio || '暂未填写个人简介。' }}</p>
        </div>
      </div>
      <dl class="profile-facts">
        <div><dt>邮箱</dt><dd>{{ authStore.currentUser.email }}</dd></div>
        <div><dt>账号状态</dt><dd>{{ authStore.currentUser.is_active ? '正常' : '已停用' }}</dd></div>
        <div><dt>加入时间</dt><dd>{{ createdAt }}</dd></div>
        <div><dt>用户编号</dt><dd>{{ authStore.currentUser.id }}</dd></div>
      </dl>
    </section>

    <div v-else class="inline-alert is-error" role="alert">当前用户信息不可用，请重新登录。</div>
  </div>
</template>
