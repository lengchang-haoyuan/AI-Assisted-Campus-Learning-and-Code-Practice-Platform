<script setup lang="ts">
import { onMounted } from 'vue'
import { ElMessage } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import NumberRoller from '@/components/NumberRoller.vue'
import WorkspaceNav from '@/components/WorkspaceNav.vue'
import { formatWorkspaceDate, getLocalDateValue, taskStatusLabels } from '@/domain/workspace'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const selectedDate = getLocalDateValue()
const utcOffsetMinutes = -new Date().getTimezoneOffset()

async function loadDashboard(): Promise<void> {
  try {
    await workspaceStore.fetchDashboard(selectedDate, utcOffsetMinutes)
  } catch {
    // Store 已保存可重试提示。
  }
}

async function completeTask(taskId: number): Promise<void> {
  try {
    await workspaceStore.completeTask(taskId)
    await workspaceStore.fetchDashboard(selectedDate, utcOffsetMinutes)
    ElMessage.success('任务已完成')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务状态更新失败，请重试'))
  }
}

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <div class="page-shell workspace-page">
    <WorkspaceNav />
    <header class="workspace-hero">
      <div>
        <p class="page-kicker">Personal Workspace</p>
        <h1>今天，从一件清晰的事开始</h1>
        <p>{{ formatWorkspaceDate(selectedDate) }}的任务、学习投入和项目进度都在这里。</p>
      </div>
      <RouterLink class="primary-command" to="/workspace/tasks">安排今日任务</RouterLink>
    </header>

    <div v-if="workspaceStore.error" class="inline-alert is-error" role="alert">
      <span>{{ workspaceStore.error }}</span>
      <button type="button" @click="loadDashboard">重试</button>
    </div>

    <div v-if="workspaceStore.loading && !workspaceStore.dashboard" class="workspace-dashboard-loading" aria-label="工作台加载中">
      <span v-for="index in 7" :key="index" />
    </div>

    <template v-else-if="workspaceStore.dashboard">
      <section class="workspace-metric-grid" aria-label="今日学习统计">
        <article>
          <NumberRoller :value="workspaceStore.dashboard.stats.today_task_completed" />
          <span>已完成任务</span>
          <small>共 {{ workspaceStore.dashboard.stats.today_task_total }} 项</small>
        </article>
        <article>
          <NumberRoller :value="workspaceStore.dashboard.stats.today_recorded_minutes" />
          <span>已记录分钟</span>
          <small>预计 {{ workspaceStore.dashboard.stats.today_estimated_minutes }} 分钟</small>
        </article>
        <article>
          <NumberRoller :value="`${workspaceStore.dashboard.stats.learning_progress}%`" />
          <span>今日学习进度</span>
          <div class="workspace-progress" aria-hidden="true">
            <span :style="{ transform: `scaleX(${workspaceStore.dashboard.stats.learning_progress / 100})` }" />
          </div>
        </article>
        <article>
          <NumberRoller :value="workspaceStore.dashboard.stats.active_project_total" />
          <span>进行中项目</span>
          <small>共 {{ workspaceStore.dashboard.stats.project_total }} 个项目</small>
        </article>
      </section>

      <div class="workspace-dashboard-grid">
        <section class="workspace-panel workspace-panel--tasks" aria-labelledby="today-tasks-title">
          <div class="panel-title-row">
            <h2 id="today-tasks-title">今日任务</h2>
            <RouterLink class="text-command" to="/workspace/tasks">查看全部</RouterLink>
          </div>
          <ul v-if="workspaceStore.dashboard.today_tasks.length" class="workspace-task-list">
            <li v-for="task in workspaceStore.dashboard.today_tasks" :key="task.id" :class="{ 'is-completed': task.status === 'completed' }">
              <div>
                <strong>{{ task.title }}</strong>
                <small>{{ task.project?.name || '个人学习' }} · {{ taskStatusLabels[task.status] }}</small>
              </div>
              <button
                v-if="task.status !== 'completed'"
                class="task-complete-command"
                type="button"
                :disabled="workspaceStore.actionTaskId === task.id"
                @click="completeTask(task.id)"
              >
                {{ workspaceStore.actionTaskId === task.id ? '处理中' : '完成' }}
              </button>
              <span v-else class="task-completed-mark" aria-label="已完成">✓</span>
            </li>
          </ul>
          <div v-else class="workspace-empty">
            <strong>今天还没有任务</strong>
            <RouterLink to="/workspace/tasks">创建第一项任务</RouterLink>
          </div>
        </section>

        <section class="workspace-panel workspace-panel--projects" aria-labelledby="recent-projects-title">
          <div class="panel-title-row">
            <h2 id="recent-projects-title">最近项目</h2>
            <RouterLink class="text-command" to="/workspace/projects">项目进度</RouterLink>
          </div>
          <div v-if="workspaceStore.dashboard.recent_projects.length" class="workspace-project-progress-list">
            <RouterLink v-for="project in workspaceStore.dashboard.recent_projects" :key="project.id" :to="`/workspace/projects/${project.id}`">
              <div class="workspace-project-progress-list__heading">
                <strong>{{ project.name }}</strong>
                <span>{{ project.progress }}%</span>
              </div>
              <div class="workspace-progress"><span :style="{ transform: `scaleX(${project.progress / 100})` }" /></div>
              <small>{{ project.completed_task_count }}/{{ project.linked_task_count }} 项任务 · {{ project.recorded_minutes }} 分钟</small>
            </RouterLink>
          </div>
          <div v-else class="workspace-empty"><strong>还没有项目</strong><RouterLink to="/projects">创建项目</RouterLink></div>
        </section>

        <section class="workspace-panel workspace-panel--records" aria-labelledby="recent-records-title">
          <div class="panel-title-row">
            <h2 id="recent-records-title">最近记录</h2>
            <RouterLink class="text-command" to="/workspace/records">记录学习</RouterLink>
          </div>
          <ol v-if="workspaceStore.dashboard.recent_records.length" class="workspace-record-list">
            <li v-for="record in workspaceStore.dashboard.recent_records" :key="record.id">
              <time :datetime="record.occurred_at">{{ formatWorkspaceDate(record.occurred_at) }}</time>
              <div><strong>{{ record.title }}</strong><small>{{ record.project?.name || '个人学习' }}</small></div>
              <span>{{ record.duration_minutes }} 分钟</span>
            </li>
          </ol>
          <div v-else class="workspace-empty"><strong>还没有学习记录</strong><RouterLink to="/workspace/records">保存第一条记录</RouterLink></div>
        </section>
      </div>
    </template>
  </div>
</template>
