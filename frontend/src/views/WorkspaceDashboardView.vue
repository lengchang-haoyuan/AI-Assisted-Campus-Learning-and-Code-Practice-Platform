<script setup lang="ts">
import { computed, onMounted } from 'vue'

import NumberRoller from '@/components/NumberRoller.vue'
import { difficultyLabels, formatProjectTime, statusLabels } from '@/domain/projects'
import { useProjectStore } from '@/stores/projects'

const projectStore = useProjectStore()
const activeProjects = computed(() =>
  projectStore.projects.filter((project) => project.status === 'in_progress'),
)
const completedProjects = computed(() =>
  projectStore.projects.filter((project) => project.status === 'completed'),
)

async function loadProjects(): Promise<void> {
  try {
    await projectStore.fetchProjects({ page: 1, pageSize: 12 })
  } catch {
    // Store 已保存可重试的用户提示。
  }
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <div class="page-shell workspace-page">
    <header class="page-header">
      <div>
        <h1>我的学习桌面</h1>
        <p>聚焦当前项目，确认下一步要推进的内容。</p>
      </div>
      <RouterLink class="primary-command" to="/projects">管理项目</RouterLink>
    </header>

    <div v-if="projectStore.listError" class="inline-alert is-error" role="alert">
      <span>{{ projectStore.listError }}</span>
      <button type="button" @click="loadProjects">重试</button>
    </div>

    <section class="workspace-stats" aria-label="项目统计">
      <div><NumberRoller :value="projectStore.page.total" /><span>全部项目</span></div>
      <div><NumberRoller :value="activeProjects.length" /><span>正在推进</span></div>
      <div><NumberRoller :value="completedProjects.length" /><span>已经完成</span></div>
    </section>

    <section class="workspace-band" aria-labelledby="active-projects-title">
      <div class="panel-title-row">
        <h2 id="active-projects-title">正在推进</h2>
        <span>{{ activeProjects.length }} 个项目</span>
      </div>
      <div v-if="projectStore.listLoading" class="compact-skeleton"><span /><span /><span /></div>
      <div v-else-if="activeProjects.length" class="workspace-project-list">
        <RouterLink v-for="project in activeProjects" :key="project.id" :to="`/projects/${project.id}`">
          <div>
            <strong>{{ project.name }}</strong>
            <span>{{ difficultyLabels[project.difficulty] }} · {{ statusLabels[project.status] }}</span>
          </div>
          <time :datetime="project.updated_at">{{ formatProjectTime(project.updated_at) }}</time>
        </RouterLink>
      </div>
      <div v-else class="empty-state compact-empty-state">
        <h3>暂无进行中的项目</h3>
        <p>可以从项目库创建项目，或调整已有项目状态。</p>
      </div>
    </section>

    <section class="workspace-band" aria-labelledby="completed-projects-title">
      <div class="panel-title-row">
        <h2 id="completed-projects-title">最近完成</h2>
        <span>{{ completedProjects.length }} 个项目</span>
      </div>
      <div v-if="completedProjects.length" class="workspace-project-list">
        <RouterLink v-for="project in completedProjects.slice(0, 5)" :key="project.id" :to="`/projects/${project.id}`">
          <div><strong>{{ project.name }}</strong><span>{{ project.language || '未设置语言' }}</span></div>
          <time :datetime="project.updated_at">{{ formatProjectTime(project.updated_at) }}</time>
        </RouterLink>
      </div>
      <div v-else class="empty-state compact-empty-state"><h3>暂无已完成项目</h3></div>
    </section>
  </div>
</template>
