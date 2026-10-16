<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { getProjectCover, getProjectCoverSrcset } from '@/assets/projectCovers'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import ProjectFlipCard from '@/components/ProjectFlipCard.vue'
import UiIcon from '@/components/UiIcon.vue'
import { formatProjectTime, getProjectStack, statusLabels } from '@/domain/projects'
import { useProjectStore } from '@/stores/projects'
import type { ProjectResponse } from '@/types/project'

const projectStore = useProjectStore()
const router = useRouter()
const activeFilter = ref('all')
const remainingSeconds = ref(25 * 60)
const timerRunning = ref(false)
let timerId: number | null = null

const filterOptions: LiquidTabOption[] = [
  { value: 'all', label: '全部' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
]

const filteredProjects = computed(() => {
  if (activeFilter.value === 'all') return projectStore.projects
  return projectStore.projects.filter((project) => project.status === activeFilter.value)
})
const recentProjects = computed(() =>
  [...projectStore.projects].sort(
    (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  ),
)
const inProgressCount = computed(
  () => projectStore.projects.filter((project) => project.status === 'in_progress').length,
)
const completedCount = computed(
  () => projectStore.projects.filter((project) => project.status === 'completed').length,
)
const featuredProject = computed(() => recentProjects.value.find((project) => project.status === 'in_progress') ?? recentProjects.value[0] ?? null)
const featuredStack = computed(() => featuredProject.value ? getProjectStack(featuredProject.value).slice(0, 2).join(' · ') : '')
const supportingProjects = computed(() => recentProjects.value.filter((project) => project.id !== featuredProject.value?.id))
const todayLabel = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date())
const timerLabel = computed(() => {
  const minutes = Math.floor(remainingSeconds.value / 60).toString().padStart(2, '0')
  const seconds = (remainingSeconds.value % 60).toString().padStart(2, '0')
  return `${minutes}:${seconds}`
})

async function loadProjects(): Promise<void> {
  try {
    await projectStore.fetchProjects({ page: 1, pageSize: 12 })
  } catch {
    // Store 已保存可重试的用户提示。
  }
}

function toggleTimer(): void {
  timerRunning.value = !timerRunning.value
  if (timerRunning.value && timerId === null) {
    timerId = window.setInterval(() => {
      if (remainingSeconds.value <= 0) {
        timerRunning.value = false
        if (timerId !== null) window.clearInterval(timerId)
        timerId = null
        return
      }
      remainingSeconds.value -= 1
    }, 1000)
  } else if (!timerRunning.value && timerId !== null) {
    window.clearInterval(timerId)
    timerId = null
  }
}

function resetTimer(): void {
  if (timerId !== null) window.clearInterval(timerId)
  timerId = null
  timerRunning.value = false
  remainingSeconds.value = 25 * 60
}

function editProject(project: ProjectResponse): void {
  void router.push({ name: 'project-detail', params: { id: project.id }, query: { edit: '1' } })
}

async function removeProject(project: ProjectResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除“${project.name}”后无法恢复。`, '确认删除项目', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
    await projectStore.deleteProject(project.id)
    ElMessage.success('项目已删除')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除失败，请重试'))
  }
}

onMounted(() => {
  void loadProjects()
})

onBeforeUnmount(() => {
  if (timerId !== null) window.clearInterval(timerId)
})
</script>

<template>
  <div class="studio-home">
    <div v-if="projectStore.listError" class="inline-alert is-error" role="alert">
      <span>{{ projectStore.listError }}</span><button type="button" @click="loadProjects">重试</button>
    </div>
    <section class="studio-home-hero" aria-labelledby="daily-desk-title">
      <div class="studio-greeting">
        <p class="studio-today">{{ todayLabel }}</p>
        <h1 id="daily-desk-title">把想法，<br />做成<span>作品。</span></h1>
        <p class="studio-greeting-copy">从今天的实践开始，积累属于你的成长。</p>
      </div>

      <article v-if="featuredProject" class="studio-featured">
        <img class="studio-featured-cover" :src="getProjectCover(featuredProject)" :srcset="getProjectCoverSrcset(featuredProject)" sizes="(max-width: 760px) calc(100vw - 32px), 60vw" :alt="`${featuredProject.name} 项目封面`" width="1200" height="600" fetchpriority="high" />
        <div class="studio-featured-content">
          <span class="studio-featured-label">继续项目</span>
          <h2><RouterLink :to="`/projects/${featuredProject.id}`">{{ featuredProject.name }}</RouterLink></h2>
          <p class="studio-featured-stack">{{ featuredStack || '技术栈待补充' }}</p>
          <div class="studio-featured-bottom">
            <div class="studio-card-progress">
              <span>项目进度 <strong>{{ featuredProject.progress }}%</strong></span>
              <div class="studio-progress" role="progressbar" :aria-label="`${featuredProject.name} 项目进度`" :aria-valuenow="featuredProject.progress" aria-valuemin="0" aria-valuemax="100"><span :style="{ transform: `scaleX(${featuredProject.progress / 100})` }" /></div>
            </div>
            <RouterLink class="primary-command" :to="`/projects/${featuredProject.id}`">继续项目 <UiIcon name="arrow" /></RouterLink>
          </div>
        </div>
      </article>
      <article v-else class="studio-featured">
        <img class="studio-featured-cover" :src="getProjectCover({})" :srcset="getProjectCoverSrcset({})" sizes="(max-width: 760px) calc(100vw - 32px), 60vw" alt="" width="1200" height="600" />
        <div v-if="projectStore.listLoading" class="compact-skeleton studio-home-loading" aria-label="项目加载中"><span v-for="index in 3" :key="index" /></div>
        <div v-else class="studio-featured-content studio-home-empty"><h2>从第一个项目开始</h2><p>记录一个想法，为它建立清晰的实践目标。</p><RouterLink class="primary-command" to="/projects">创建项目 <UiIcon name="plus" /></RouterLink></div>
      </article>

      <section class="studio-focus" aria-labelledby="focus-title">
        <h2 id="focus-title">本次专注</h2>
        <div class="studio-focus-row">
          <p class="focus-time" aria-label="剩余专注时间">{{ timerLabel }}</p>
          <button class="secondary-command" type="button" @click="toggleTimer">{{ timerRunning ? '暂停专注' : '开始专注' }}</button>
          <button class="text-command" type="button" @click="resetTimer">重置</button>
        </div>
        <div v-if="timerRunning" class="focus-progress" aria-hidden="true"><span :style="{ transform: `scaleX(${remainingSeconds / (25 * 60)})` }" /></div>
      </section>
    </section>

    <section class="studio-recent" aria-labelledby="studio-recent-title">
      <div class="panel-title-row"><h2 id="studio-recent-title">最近项目</h2><RouterLink class="text-command studio-arrow-link" to="/projects">查看全部 <UiIcon name="arrow" /></RouterLink></div>
      <div class="studio-recent-layout">
        <div class="studio-recent-list">
          <article v-for="project in supportingProjects.slice(0, 2)" :key="project.id" class="studio-recent-project">
            <RouterLink :to="`/projects/${project.id}`" tabindex="-1" aria-hidden="true"><img :src="getProjectCover(project)" :srcset="getProjectCoverSrcset(project)" sizes="(max-width: 760px) 106px, (max-width: 1280px) 35vw, 20vw" alt="" width="800" height="420" loading="lazy" /></RouterLink>
            <div><h3><RouterLink :to="`/projects/${project.id}`" :title="project.name">{{ project.name }}</RouterLink></h3><p>{{ getProjectStack(project).slice(0, 2).join(' · ') || '技术栈待补充' }}</p><span class="status-chip" :data-status="project.status">{{ statusLabels[project.status] }}</span><small>更新于 {{ formatProjectTime(project.updated_at) }}</small></div>
          </article>
          <p v-if="!projectStore.listLoading && recentProjects.length === 0" class="muted-copy">创建项目后，最近的实践会出现在这里。</p>
          <p v-else-if="!projectStore.listLoading && supportingProjects.length === 0" class="muted-copy">最近的项目已置顶展示，可进入项目库查看全部。</p>
        </div>
        <div class="studio-data-entry"><h3><UiIcon name="data" />学习与社区数据</h3><p>查看你的学习时长、项目进度与社区互动。</p><RouterLink class="studio-arrow-link" to="/analytics">查看学习数据 <UiIcon name="arrow" /></RouterLink></div>
      </div>
    </section>

    <details class="studio-project-tools">
      <summary><span>我的项目广场</span><span class="studio-loaded-count">{{ projectStore.page.total }} 个项目 · 本页 {{ inProgressCount }} 个进行中 · {{ completedCount }} 个已完成</span></summary>
      <div class="panel-title-row studio-project-toolbar"><LiquidTabs v-model="activeFilter" :options="filterOptions" ariaLabel="项目状态筛选" /><RouterLink class="primary-command compact-command" to="/projects">新建项目</RouterLink></div>
      <div v-if="projectStore.listLoading" class="project-grid-loading" aria-label="项目加载中"><span v-for="index in 3" :key="index" /></div>
      <div v-else-if="filteredProjects.length" class="project-list-grid"><ProjectFlipCard v-for="project in filteredProjects.slice(0, 3)" :key="project.id" :project="project" :image-url="getProjectCover(project)" :image-srcset="getProjectCoverSrcset(project)" @edit="editProject" @delete="removeProject" /></div>
      <div v-else class="empty-state"><h3>还没有符合条件的项目</h3><p>创建第一个项目，开始记录技术栈和交付目标。</p><RouterLink class="primary-command" to="/projects">创建项目</RouterLink></div>
    </details>
    <nav class="studio-quick-links" aria-label="快速入口"><RouterLink to="/projects">项目管理</RouterLink><RouterLink to="/workspace/dashboard">学习桌面</RouterLink><RouterLink to="/profile">个人资料</RouterLink></nav>
  </div>
</template>
