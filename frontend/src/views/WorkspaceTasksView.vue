<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import TaskForm from '@/components/TaskForm.vue'
import WorkspaceNav from '@/components/WorkspaceNav.vue'
import { formatWorkspaceDate, getLocalDateValue, priorityLabels, taskStatusLabels } from '@/domain/workspace'
import { useProjectStore } from '@/stores/projects'
import { useWorkspaceStore } from '@/stores/workspace'
import type { TaskCreateInput } from '@/types/workspace'

const workspaceStore = useWorkspaceStore()
const projectStore = useProjectStore()
const today = getLocalDateValue()
const scope = ref('today')
const pageNumber = ref(1)
const showForm = ref(false)
const scopeOptions: LiquidTabOption[] = [
  { value: 'today', label: '今天' },
  { value: 'all', label: '全部任务' },
]
const heading = computed(() => scope.value === 'today' ? '今天要完成什么' : '全部任务')

async function loadTasks(): Promise<void> {
  try {
    await workspaceStore.fetchTasks(
      { page: pageNumber.value, pageSize: 20 },
      scope.value === 'today' ? today : undefined,
    )
  } catch {
    // Store 已保存可重试提示。
  }
}

async function changeScope(value: string): Promise<void> {
  scope.value = value
  pageNumber.value = 1
  await loadTasks()
}

async function createTask(input: TaskCreateInput): Promise<void> {
  try {
    await workspaceStore.createTask(input)
    showForm.value = false
    if (scope.value === 'today' && input.scheduled_date !== today) scope.value = 'all'
    await loadTasks()
    ElMessage.success('任务已创建')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务创建失败，请重试'))
  }
}

async function completeTask(taskId: number): Promise<void> {
  try {
    await workspaceStore.completeTask(taskId)
    ElMessage.success('任务已完成')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务状态更新失败，请重试'))
  }
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadTasks()
}

onMounted(() => {
  void loadTasks()
  void projectStore.fetchProjects({ page: 1, pageSize: 100 }).catch(() => undefined)
})
</script>

<template>
  <div class="page-shell workspace-page">
    <WorkspaceNav />
    <header class="page-header">
      <div><p class="page-kicker">Daily Tasks</p><h1>{{ heading }}</h1><p>把计划拆成可以真正完成的动作。</p></div>
      <button class="primary-command" type="button" @click="showForm = !showForm">{{ showForm ? '收起表单' : '创建任务' }}</button>
    </header>

    <section v-if="showForm" class="workspace-panel workspace-editor" aria-label="创建任务">
      <TaskForm :projects="projectStore.projects" :submitting="workspaceStore.saving" @submit="createTask" @cancel="showForm = false" />
    </section>

    <div class="workspace-filter-row">
      <LiquidTabs :model-value="scope" :options="scopeOptions" ariaLabel="任务范围" @update:model-value="changeScope" />
      <span>{{ workspaceStore.taskPage.total }} 项任务</span>
    </div>

    <div v-if="workspaceStore.error" class="inline-alert is-error" role="alert"><span>{{ workspaceStore.error }}</span><button type="button" @click="loadTasks">重试</button></div>
    <div v-if="workspaceStore.loading" class="workspace-list-loading"><span v-for="index in 5" :key="index" /></div>
    <ul v-else-if="workspaceStore.taskPage.items.length" class="workspace-task-board">
      <li v-for="task in workspaceStore.taskPage.items" :key="task.id" :class="{ 'is-completed': task.status === 'completed' }">
        <div class="task-priority" :data-priority="task.priority"><span />{{ priorityLabels[task.priority] }}</div>
        <div class="task-main-copy">
          <strong>{{ task.title }}</strong>
          <p v-if="task.description">{{ task.description }}</p>
          <small>{{ formatWorkspaceDate(task.scheduled_date) }} · {{ task.project?.name || '个人学习' }} · {{ task.estimated_minutes ? `${task.estimated_minutes} 分钟` : '未估时' }}</small>
        </div>
        <span class="status-chip">{{ taskStatusLabels[task.status] }}</span>
        <button v-if="task.status !== 'completed'" class="secondary-command compact-command" type="button" :disabled="workspaceStore.actionTaskId === task.id" @click="completeTask(task.id)">
          {{ workspaceStore.actionTaskId === task.id ? '处理中' : '标记完成' }}
        </button>
        <span v-else class="task-completed-mark" aria-label="已完成">✓</span>
      </li>
    </ul>
    <section v-else class="empty-state"><h2>{{ scope === 'today' ? '今天还没有安排任务' : '还没有任务' }}</h2><p>创建一项清晰、可以完成的学习任务。</p><button class="primary-command" type="button" @click="showForm = true">创建任务</button></section>

    <nav v-if="workspaceStore.taskPage.total_pages > 1" class="pagination" aria-label="任务分页">
      <button type="button" :disabled="pageNumber <= 1 || workspaceStore.loading" @click="changePage(pageNumber - 1)">上一页</button>
      <span>第 {{ pageNumber }} / {{ workspaceStore.taskPage.total_pages }} 页</span>
      <button type="button" :disabled="pageNumber >= workspaceStore.taskPage.total_pages || workspaceStore.loading" @click="changePage(pageNumber + 1)">下一页</button>
    </nav>
  </div>
</template>
