<script setup lang="ts">
import { computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import NumberRoller from '@/components/NumberRoller.vue'
import WorkspaceNav from '@/components/WorkspaceNav.vue'
import { difficultyLabels, statusLabels } from '@/domain/projects'
import { formatWorkspaceDate, recordTypeLabels, taskStatusLabels } from '@/domain/workspace'
import { useWorkspaceStore } from '@/stores/workspace'

const route = useRoute()
const workspaceStore = useWorkspaceStore()
const projectId = computed(() => Number(route.params.id))

async function loadProject(): Promise<void> {
  if (!Number.isInteger(projectId.value) || projectId.value < 1) return
  try {
    await workspaceStore.fetchProject(projectId.value)
  } catch {
    // Store 已保存可重试提示。
  }
}

async function completeTask(taskId: number): Promise<void> {
  try {
    await workspaceStore.completeTask(taskId)
    await workspaceStore.fetchProject(projectId.value)
    ElMessage.success('任务已完成，项目进度已更新')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务状态更新失败，请重试'))
  }
}

watch(projectId, () => { void loadProject() }, { immediate: true })
</script>

<template>
  <div class="page-shell workspace-page">
    <WorkspaceNav />
    <RouterLink class="back-link" to="/workspace/projects">← 返回项目进度</RouterLink>
    <div v-if="workspaceStore.error" class="inline-alert is-error" role="alert"><span>{{ workspaceStore.error }}</span><button type="button" @click="loadProject">重试</button></div>
    <div v-if="workspaceStore.loading" class="detail-skeleton"><span /><span /><span /></div>
    <template v-else-if="workspaceStore.projectDetail">
      <header class="workspace-project-detail-header">
        <div>
          <p class="page-kicker">{{ difficultyLabels[workspaceStore.projectDetail.difficulty] }} · {{ statusLabels[workspaceStore.projectDetail.status] }}</p>
          <h1>{{ workspaceStore.projectDetail.name }}</h1>
          <p>{{ workspaceStore.projectDetail.description || '暂无项目说明' }}</p>
        </div>
        <div class="workspace-project-score"><NumberRoller :value="`${workspaceStore.projectDetail.progress}%`" /><span>项目进度</span></div>
      </header>
      <div class="workspace-progress workspace-progress--large"><span :style="{ transform: `scaleX(${workspaceStore.projectDetail.progress / 100})` }" /></div>

      <section class="workspace-metric-grid workspace-metric-grid--three" aria-label="项目学习数据">
        <article><NumberRoller :value="workspaceStore.projectDetail.linked_task_count" /><span>关联任务</span><small>{{ workspaceStore.projectDetail.completed_task_count }} 项已完成</small></article>
        <article><NumberRoller :value="workspaceStore.projectDetail.recorded_minutes" /><span>学习分钟</span><small>来自真实学习记录</small></article>
        <article><NumberRoller :value="workspaceStore.projectDetail.recent_records.length" /><span>近期记录</span><small>最近 8 条以内</small></article>
      </section>

      <div class="workspace-project-detail-grid">
        <section class="workspace-panel workspace-panel--tasks">
          <div class="panel-title-row"><h2>项目任务</h2><RouterLink class="text-command" to="/workspace/tasks">管理任务</RouterLink></div>
          <ul v-if="workspaceStore.projectDetail.recent_tasks.length" class="workspace-task-list">
            <li v-for="task in workspaceStore.projectDetail.recent_tasks" :key="task.id" :class="{ 'is-completed': task.status === 'completed' }">
              <div><strong>{{ task.title }}</strong><small>{{ formatWorkspaceDate(task.scheduled_date) }} · {{ taskStatusLabels[task.status] }}</small></div>
              <button v-if="task.status !== 'completed'" class="task-complete-command" type="button" :disabled="workspaceStore.actionTaskId === task.id" @click="completeTask(task.id)">{{ workspaceStore.actionTaskId === task.id ? '处理中' : '完成' }}</button>
              <span v-else class="task-completed-mark" aria-label="已完成">✓</span>
            </li>
          </ul>
          <div v-else class="workspace-empty"><strong>该项目还没有关联任务</strong><RouterLink to="/workspace/tasks">创建任务</RouterLink></div>
        </section>
        <section class="workspace-panel workspace-panel--records">
          <div class="panel-title-row"><h2>学习记录</h2><RouterLink class="text-command" to="/workspace/records">添加记录</RouterLink></div>
          <ol v-if="workspaceStore.projectDetail.recent_records.length" class="workspace-record-list">
            <li v-for="record in workspaceStore.projectDetail.recent_records" :key="record.id">
              <time :datetime="record.occurred_at">{{ formatWorkspaceDate(record.occurred_at) }}</time>
              <div><strong>{{ record.title }}</strong><small>{{ recordTypeLabels[record.record_type] }}</small></div>
              <span>{{ record.duration_minutes }} 分钟</span>
            </li>
          </ol>
          <div v-else class="workspace-empty"><strong>该项目还没有学习记录</strong><RouterLink to="/workspace/records">保存记录</RouterLink></div>
        </section>
      </div>
    </template>
  </div>
</template>
