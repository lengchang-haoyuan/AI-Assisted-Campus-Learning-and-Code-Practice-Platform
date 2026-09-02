<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const searchQuery = ref(typeof route.query.q === 'string' ? route.query.q : '')

const userInitial = computed(() => authStore.currentUser?.username.slice(0, 1).toUpperCase() || 'S')

function search(): void {
  const query = searchQuery.value.trim()
  void router.push({ name: 'projects', query: query ? { q: query } : {} })
}

function logout(): void {
  authStore.logout()
  void router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header class="app-topbar">
      <RouterLink class="app-brand" to="/">ScholarHub</RouterLink>

      <nav class="primary-navigation" aria-label="主导航">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/community">社区</RouterLink>
        <RouterLink to="/projects">项目库</RouterLink>
        <RouterLink to="/workspace/dashboard">我的桌面</RouterLink>
        <RouterLink to="/learning">学习系统</RouterLink>
        <RouterLink to="/workflows">工作流</RouterLink>
        <RouterLink to="/analytics">数据</RouterLink>
      </nav>

      <form class="global-search" role="search" @submit.prevent="search">
        <label class="sr-only" for="global-search-input">搜索项目或技术栈</label>
        <input
          id="global-search-input"
          v-model="searchQuery"
          type="search"
          placeholder="搜索项目或技术栈"
        />
        <button type="submit">搜索</button>
      </form>

      <div class="profile-actions">
        <RouterLink class="profile-link" to="/profile">
          <span class="avatar" aria-hidden="true">{{ userInitial }}</span>
          <span class="profile-copy">
            <strong>{{ authStore.currentUser?.username || '同学' }}</strong>
            <small>个人资料</small>
          </span>
        </RouterLink>
        <button class="logout-command" type="button" @click="logout">退出</button>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
