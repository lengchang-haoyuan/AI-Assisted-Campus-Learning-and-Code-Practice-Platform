<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { getCampusMe } from '@/api/campus'
import UiIcon from '@/components/UiIcon.vue'
import brandMark from '@/assets/campus-studio/brand-mark.png'
import '@/styles/campus-studio.css'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const searchQuery = ref(typeof route.query.q === 'string' ? route.query.q : '')
const isCampusAdmin = ref(false)
const hasCampusMembership = ref(false)
const searchOpen = ref(false)
const menuOpen = ref(false)
const navigationDialog = ref<HTMLDialogElement | null>(null)
const primaryDestinations = [
  { to: '/', label: '首页', icon: 'home' },
  { to: '/community', label: '社区', icon: 'community' },
  { to: '/projects', label: '项目库', icon: 'project' },
  { to: '/workspace/dashboard', label: '我的桌面', icon: 'workspace' },
  { to: '/learning', label: '学习系统', icon: 'learning' },
  { to: '/workflows', label: '工作流', icon: 'workflow' },
  { to: '/analytics', label: '数据', icon: 'data' },
] as const
const mobileDestinations = [primaryDestinations[0], primaryDestinations[2], primaryDestinations[4], primaryDestinations[6]]

const userInitial = computed(() => authStore.currentUser?.username.slice(0, 1).toUpperCase() || 'S')

function isActive(path: string): boolean {
  return path === '/' ? route.path === '/' : route.path === path || route.path.startsWith(`${path}/`)
}

function openNavigation(): void {
  navigationDialog.value?.showModal()
  menuOpen.value = true
}

function closeNavigation(): void {
  navigationDialog.value?.close()
  menuOpen.value = false
}

watch(() => route.fullPath, () => {
  closeNavigation()
  searchOpen.value = false
})

onMounted(async () => {
  try {
    const membership = (await getCampusMe()).membership
    hasCampusMembership.value = membership?.status === 'active'
    isCampusAdmin.value = membership?.role === 'administrator' && membership.status === 'active'
  } catch {
    hasCampusMembership.value = false
    isCampusAdmin.value = false
  }
})

function search(): void {
  const query = searchQuery.value.trim()
  void router.push({ name: 'projects', query: query ? { q: query } : {} })
}

function logout(): void {
  authStore.logout(router.resolve({ name: 'login' }).href)
}
</script>

<template>
  <div class="app-shell campus-studio">
    <header class="app-topbar">
      <RouterLink class="app-brand" to="/" aria-label="ScholarHub 首页">
        <img :src="brandMark" width="40" height="40" alt="" />
        <span>ScholarHub</span>
      </RouterLink>

      <nav class="primary-navigation" aria-label="主导航">
        <RouterLink v-for="destination in primaryDestinations" :key="destination.to" :to="destination.to" :class="{ 'is-current': isActive(destination.to) }">
          {{ destination.label }}
        </RouterLink>
      </nav>

      <button class="studio-mobile-search studio-icon-button" type="button" aria-label="打开项目搜索" :aria-expanded="searchOpen" aria-controls="studio-global-search" @click="searchOpen = !searchOpen">
        <UiIcon name="search" />
      </button>
      <form id="studio-global-search" class="global-search" :class="{ 'is-open': searchOpen }" role="search" @submit.prevent="search">
        <label class="sr-only" for="global-search-input">搜索项目或技术栈</label>
        <input
          id="global-search-input"
          v-model="searchQuery"
          type="search"
          placeholder="搜索项目或技术栈"
        />
        <button type="submit" aria-label="搜索"><UiIcon name="search" /><span class="sr-only">搜索</span></button>
      </form>

      <div class="profile-actions">
        <RouterLink class="profile-link" to="/profile" :aria-label="`${authStore.currentUser?.username || '同学'}的个人资料`">
          <span class="avatar" aria-hidden="true">{{ userInitial }}</span>
          <span class="profile-copy">
            <strong>{{ authStore.currentUser?.username || '同学' }}</strong>
            <small>个人资料</small>
          </span>
        </RouterLink>
        <button class="logout-command" type="button" @click="logout">退出</button>
        <button v-if="hasCampusMembership" class="studio-desktop-more studio-icon-button" type="button" aria-label="校园功能" :aria-expanded="menuOpen" @click="openNavigation"><UiIcon name="more" /></button>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>

    <nav class="studio-mobile-navigation" aria-label="手机主导航">
      <RouterLink v-for="destination in mobileDestinations" :key="destination.to" :to="destination.to" :class="{ 'is-current': isActive(destination.to) }">
        <UiIcon :name="destination.icon" />
        <span>{{ destination.to === '/learning' ? '学习' : destination.label }}</span>
      </RouterLink>
      <button type="button" :aria-expanded="menuOpen" aria-controls="studio-navigation-dialog" @click="openNavigation"><UiIcon name="more" /><span>更多</span></button>
    </nav>

    <dialog id="studio-navigation-dialog" ref="navigationDialog" class="studio-navigation-dialog" aria-labelledby="studio-navigation-title" @close="menuOpen = false">
      <div class="panel-title-row"><h2 id="studio-navigation-title">全部功能</h2><button class="studio-icon-button" type="button" aria-label="关闭导航" @click="closeNavigation"><UiIcon name="close" /></button></div>
      <nav aria-label="全部功能导航">
        <RouterLink v-for="destination in primaryDestinations" :key="destination.to" :to="destination.to" :class="{ 'is-current': isActive(destination.to) }" @click="closeNavigation"><UiIcon :name="destination.icon" />{{ destination.label }}</RouterLink>
        <RouterLink v-if="hasCampusMembership" to="/community/governance" @click="closeNavigation">社区治理</RouterLink>
        <RouterLink v-if="hasCampusMembership" to="/campus/classes" @click="closeNavigation">教学班</RouterLink>
        <RouterLink v-if="hasCampusMembership && !isCampusAdmin" to="/campus/submissions" @click="closeNavigation">成果</RouterLink>
        <RouterLink v-if="hasCampusMembership" to="/notifications" @click="closeNavigation">通知</RouterLink>
        <RouterLink v-if="isCampusAdmin" to="/campus/admin/accounts" @click="closeNavigation">校园管理</RouterLink>
        <RouterLink to="/profile" @click="closeNavigation"><UiIcon name="profile" />个人资料</RouterLink>
      </nav>
      <button class="secondary-command studio-dialog-logout" type="button" @click="logout">退出登录</button>
    </dialog>
  </div>
</template>
