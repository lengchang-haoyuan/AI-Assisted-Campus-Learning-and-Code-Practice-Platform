<script setup lang="ts">
import { onMounted, ref } from 'vue'

import NumberRoller from '@/components/NumberRoller.vue'
import WorkspaceNav from '@/components/WorkspaceNav.vue'
import { difficultyLabels, formatProjectTime, statusLabels } from '@/domain/projects'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const pageNumber = ref(1)

async function loadProjects(): Promise<void> {
  try {
    await workspaceStore.fetchProjects({ page: pageNumber.value, pageSize: 12 })
  } catch {
    // Store 已保存可重试提示。
  }
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadProjects()
}

onMounted(() => { void loadProjects() })
</script>

<template>
  <div class="page-shell workspace-page">
    <WorkspaceNav />
    <header class="page-header">
      <div><p class="page-kicker">Project Progress</p><h1>项目进度</h1><p>进度由关联任务的真实完成情况计算。</p></div>
      <RouterLink class="primary-command" to="/projects">管理项目</RouterLink>
    </header>
    <div v-if="workspaceStore.error" class="inline-alert is-error" role="alert"><span>{{ workspaceStore.error }}</span><button type="button" @click="loadProjects">重试</button></div>
    <div v-if="workspaceStore.loading" class="workspace-project-grid workspace-list-loading"><span v-for="index in 6" :key="index" /></div>
    <section v-else-if="workspaceStore.projectPage.items.length" class="workspace-project-grid" aria-label="工作台项目列表">
      <RouterLink v-for="project in workspaceStore.projectPage.items" :key="project.id" class="workspace-project-card" :to="`/workspace/projects/${project.id}`">
        <div class="workspace-project-card__top"><span class="status-chip">{{ statusLabels[project.status] }}</span><small>{{ difficultyLabels[project.difficulty] }}</small></div>
        <h2>{{ project.name }}</h2>
        <p>{{ project.description || '暂无项目说明' }}</p>
        <div class="workspace-project-card__progress"><NumberRoller :value="`${project.progress}%`" /><span>{{ project.completed_task_count }}/{{ project.linked_task_count }} 项任务</span></div>
        <div class="workspace-progress"><span :style="{ transform: `scaleX(${project.progress / 100})` }" /></div>
        <footer><span>{{ project.recorded_minutes }} 学习分钟</span><time :datetime="project.updated_at">{{ formatProjectTime(project.updated_at) }}</time></footer>
      </RouterLink>
    </section>
    <section v-else class="empty-state"><h2>还没有项目</h2><p>先在项目库创建项目，再为它关联任务和学习记录。</p><RouterLink class="primary-command" to="/projects">创建项目</RouterLink></section>
    <nav v-if="workspaceStore.projectPage.total_pages > 1" class="pagination" aria-label="项目进度分页">
      <button type="button" :disabled="pageNumber <= 1 || workspaceStore.loading" @click="changePage(pageNumber - 1)">上一页</button>
      <span>第 {{ pageNumber }} / {{ workspaceStore.projectPage.total_pages }} 页</span>
      <button type="button" :disabled="pageNumber >= workspaceStore.projectPage.total_pages || workspaceStore.loading" @click="changePage(pageNumber + 1)">下一页</button>
    </nav>
  </div>
</template>
