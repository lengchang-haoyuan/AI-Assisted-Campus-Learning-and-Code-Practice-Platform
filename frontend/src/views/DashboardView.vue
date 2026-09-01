<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { getProjectCover } from '@/assets/projectCovers'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import ProjectFlipCard from '@/components/ProjectFlipCard.vue'
import { formatProjectTime, statusLabels } from '@/domain/projects'
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
  <div class="dashboard-board">
    <aside class="board-panel daily-desk" aria-labelledby="daily-desk-title">
      <div class="panel-title-row">
        <h1 id="daily-desk-title">我的今日桌面</h1>
        <RouterLink class="text-command" to="/projects">全部项目</RouterLink>
      </div>

      <div v-if="projectStore.listLoading" class="compact-skeleton" aria-label="项目加载中">
        <span v-for="index in 4" :key="index" />
      </div>
      <ul v-else class="today-projects">
        <li v-for="project in projectStore.projects.slice(0, 4)" :key="project.id">
          <span class="project-state-dot" :data-status="project.status" />
          <RouterLink :to="`/projects/${project.id}`">{{ project.name }}</RouterLink>
          <small>{{ statusLabels[project.status] }}</small>
        </li>
        <li v-if="projectStore.projects.length === 0" class="muted-row">暂无项目</li>
      </ul>

      <section class="focus-block" aria-labelledby="focus-title">
        <div class="panel-title-row">
          <h2 id="focus-title">本次专注</h2>
          <button class="text-command" type="button" @click="resetTimer">重置</button>
        </div>
        <p class="focus-time">{{ timerLabel }}</p>
        <div class="focus-progress" aria-hidden="true">
          <span :style="{ transform: `scaleX(${remainingSeconds / (25 * 60)})` }" />
        </div>
        <button class="focus-command" type="button" @click="toggleTimer">
          {{ timerRunning ? '暂停专注' : '开始专注' }}
        </button>
      </section>

      <section class="desk-stat" aria-label="项目统计">
        <div>
          <NumberRoller :value="projectStore.page.total" />
          <span>项目总数</span>
        </div>
        <div>
          <NumberRoller :value="inProgressCount" />
          <span>进行中</span>
        </div>
      </section>
    </aside>

    <section class="board-panel project-plaza" aria-labelledby="project-plaza-title">
      <div class="panel-title-row plaza-heading">
        <h2 id="project-plaza-title">我的项目广场</h2>
        <RouterLink class="primary-command compact-command" to="/projects">新建项目</RouterLink>
      </div>

      <LiquidTabs v-model="activeFilter" :options="filterOptions" :ariaLabel="'项目状态筛选'" />

      <div v-if="projectStore.listError" class="inline-alert is-error" role="alert">
        <span>{{ projectStore.listError }}</span>
        <button type="button" @click="loadProjects">重试</button>
      </div>

      <div v-if="projectStore.listLoading" class="project-grid-loading" aria-label="项目加载中">
        <span v-for="index in 3" :key="index" />
      </div>

      <div v-else-if="filteredProjects.length > 0" class="project-showcase">
        <ProjectFlipCard
          v-for="(project, index) in filteredProjects.slice(0, 3)"
          :key="project.id"
          :project="project"
          :image-url="getProjectCover(project.id, index)"
          :featured="index === 0"
          @edit="editProject"
          @delete="removeProject"
        />
      </div>

      <div v-else-if="!projectStore.listLoading" class="empty-state">
        <h3>还没有符合条件的项目</h3>
        <p>创建第一个项目，开始记录技术栈和交付目标。</p>
        <RouterLink class="primary-command" to="/projects">创建项目</RouterLink>
      </div>
    </section>

    <aside class="board-panel project-pulse" aria-labelledby="project-pulse-title">
      <div class="panel-title-row">
        <h2 id="project-pulse-title">项目脉搏</h2>
        <span class="live-indicator">实时</span>
      </div>

      <section class="pulse-section">
        <h3>最近更新</h3>
        <ul class="pulse-list">
          <li v-for="project in recentProjects.slice(0, 4)" :key="project.id">
            <span class="avatar is-small">{{ project.name.slice(0, 1) }}</span>
            <div>
              <RouterLink :to="`/projects/${project.id}`">{{ project.name }}</RouterLink>
              <small>{{ formatProjectTime(project.updated_at) }}</small>
            </div>
          </li>
          <li v-if="recentProjects.length === 0" class="muted-row">暂无更新</li>
        </ul>
      </section>

      <section class="pulse-section">
        <h3>状态分布</h3>
        <dl class="status-summary">
          <div><dt>进行中</dt><dd>{{ inProgressCount }}</dd></div>
          <div><dt>已完成</dt><dd>{{ completedCount }}</dd></div>
          <div><dt>其他状态</dt><dd>{{ Math.max(0, projectStore.page.total - inProgressCount - completedCount) }}</dd></div>
        </dl>
      </section>

      <section class="pulse-numbers" aria-label="本页项目数据">
        <div><NumberRoller :value="projectStore.page.total" /><span>全部项目</span></div>
        <div><NumberRoller :value="completedCount" /><span>完成项目</span></div>
      </section>
    </aside>

    <nav class="quick-strip" aria-label="快速入口">
      <strong>快速入口</strong>
      <RouterLink to="/projects">项目管理 <span>创建、编辑和删除</span></RouterLink>
      <RouterLink to="/workspace/dashboard">学习桌面 <span>查看项目进度</span></RouterLink>
      <RouterLink to="/profile">个人资料 <span>确认账户信息</span></RouterLink>
    </nav>
  </div>
</template>
