<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import { getLearningTask, listPlans } from '@/api/learning'
import { listProjects } from '@/api/projects'
import LearningNav from '@/components/LearningNav.vue'
import LearningTaskEditor from '@/components/LearningTaskEditor.vue'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import { getLocalDateValue, priorityLabels, taskStatusLabels } from '@/domain/workspace'
import { useLearningStore } from '@/stores/learning'
import { useAuthStore } from '@/stores/auth'
import type { LearningPlanResponse, LearningTaskCreateInput, LearningTaskResponse } from '@/types/learning'
import type { ProjectResponse } from '@/types/project'
import type { TaskStatus } from '@/types/workspace'

const learningStore = useLearningStore()
const route = useRoute(), auth = useAuthStore()
const locatedTask = ref<LearningTaskResponse | null>(null), locatedError = ref<string | null>(null), locating = ref(false)
let locatedController: AbortController | undefined, locatedGeneration = 0, locatedRequest = 0
function sourceLinks(description: string | null): string[] {
  if (!description) return []
  return [...new Set(description.match(/\/offline-analytics\?batch_id=[\da-f-]{36}(?:&dataset_kind=(?:business|controlled))?|\/projects\/\d+\/practice\?session=[\da-f-]{36}/gi) ?? [])]
}
function isLocatedRequestCurrent(id: number, ticket: number): boolean {
  return ticket === locatedGeneration && Number(route.query.task_id) === id && auth.token !== null && auth.currentUser !== null
}
async function refreshLocatedTask(id: number, ticket: number): Promise<void> {
  if (!isLocatedRequestCurrent(id, ticket)) return
  const request = ++locatedRequest
  locatedController?.abort()
  locatedController = new AbortController(); locating.value = true
  locatedError.value = null
  try {
    const result = await getLearningTask(id, locatedController.signal)
    if (request === locatedRequest && isLocatedRequestCurrent(id, ticket)) locatedTask.value = result
  } catch (cause: unknown) {
    if (request === locatedRequest && isLocatedRequestCurrent(id, ticket)) locatedError.value = getApiErrorMessage(cause, '所定位任务不可读取，请核对当前登录身份')
  } finally { if (request === locatedRequest && isLocatedRequestCurrent(id, ticket)) locating.value = false }
}
watch(() => [route.query.task_id, auth.token, auth.currentUser?.id], async () => {
  const ticket = ++locatedGeneration
  locatedController?.abort(); locatedTask.value = null; locatedError.value = null; locating.value = false
  if (!route.query.task_id || !auth.token || !auth.currentUser) return
  const id = Number(route.query.task_id)
  if (!Number.isSafeInteger(id) || id < 1) { locatedError.value = '任务编号无效，请从建议应用结果重新打开'; return }
  await refreshLocatedTask(id, ticket)
}, { immediate: true, flush: 'sync' })
onScopeDispose(() => { ++locatedGeneration; locatedController?.abort() })
const planOptions = ref<LearningPlanResponse[]>([])
const projectOptions = ref<ProjectResponse[]>([])
const scope = ref('today')
const pageNumber = ref(1)
const editingTask = ref<LearningTaskResponse | null>(null)
const showEditor = ref(false)
const today = getLocalDateValue()
const scopeOptions: LiquidTabOption[] = [
  { value: 'today', label: '今天' },
  { value: 'all', label: '全部任务' },
]
const completedCount = computed(
  () => learningStore.taskPage.items.filter((task) => task.status === 'completed').length,
)

async function loadTasks(): Promise<void> {
  await learningStore.fetchTasks(
    { page: pageNumber.value, pageSize: 20 },
    scope.value === 'today' ? { scheduledDate: today } : {},
  )
}

async function loadReferences(): Promise<void> {
  const [plans, projects] = await Promise.all([
    listPlans({ page: 1, pageSize: 100 }),
    listProjects({ page: 1, pageSize: 100 }),
  ])
  planOptions.value = plans.items
  projectOptions.value = projects.items
}

async function loadPlanOptions(): Promise<void> {
  planOptions.value = (await listPlans({ page: 1, pageSize: 100 })).items
}

function openEditor(task: LearningTaskResponse | null = null): void {
  editingTask.value = task
  showEditor.value = true
}

function closeEditor(): void {
  editingTask.value = null
  showEditor.value = false
}

async function saveTask(input: LearningTaskCreateInput & { status?: TaskStatus }): Promise<void> {
  const wasEditing = editingTask.value !== null
  const taskId = editingTask.value?.id, ticket = locatedGeneration
  try {
    await learningStore.saveTask(input, taskId)
    if (taskId !== undefined) await refreshLocatedTask(taskId, ticket)
    closeEditor()
    await Promise.all([loadTasks(), loadPlanOptions()])
    ElMessage.success(wasEditing ? '任务已更新' : '任务已创建')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务保存失败，请重试'))
  }
}

async function completeTask(task: LearningTaskResponse): Promise<void> {
  const ticket = locatedGeneration
  try {
    await learningStore.completeTask(task.id)
    await refreshLocatedTask(task.id, ticket)
    await loadPlanOptions()
    ElMessage.success('任务已完成，计划进度已同步')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务完成失败，请重试'))
  }
}

async function removeTask(task: LearningTaskResponse): Promise<void> {
  const ticket = locatedGeneration
  try {
    await ElMessageBox.confirm(`确定删除任务“${task.title}”吗？`, '删除任务', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning',
    })
    await learningStore.removeTask(task.id)
    if (isLocatedRequestCurrent(task.id, ticket)) {
      ++locatedGeneration; locatedController?.abort()
      locatedTask.value = null; locatedError.value = null; locating.value = false
    }
    await Promise.all([loadTasks(), loadPlanOptions()])
    ElMessage.success('任务已删除')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '任务删除失败，请重试'))
    }
  }
}

async function changeScope(value: string): Promise<void> {
  scope.value = value
  pageNumber.value = 1
  await loadTasks()
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadTasks()
}

onMounted(() => {
  void Promise.all([loadTasks(), loadReferences()]).catch(() => undefined)
})
</script>

<template>
  <div class="page-shell workspace-page learning-page">
    <LearningNav />
    <header class="page-header learning-task-header">
      <div><p class="page-kicker">Daily Learning</p><h1>每日任务</h1><p>任务完成与计划进度在同一事务中更新，刷新后仍保持一致。</p></div>
      <button class="primary-command" type="button" @click="openEditor()">创建任务</button>
    </header>

    <p v-if="locating" role="status">正在定位任务与建议来源…</p>
    <p v-if="locatedError" class="inline-alert is-error" role="alert">{{ locatedError }}</p>
    <section v-if="locatedTask" class="workspace-panel" aria-label="所定位任务与来源" :data-located-task="locatedTask.id">
      <h2>{{ locatedTask.title }}</h2><p>{{ locatedTask.scheduled_date }} · {{ locatedTask.project?.name || '无关联项目' }} · {{ taskStatusLabels[locatedTask.status] }}</p>
      <p style="white-space: pre-wrap; overflow-wrap: anywhere">{{ locatedTask.description }}</p>
      <div class="learning-row-actions"><RouterLink v-for="link in sourceLinks(locatedTask.description)" :key="link" :to="link">{{ link.startsWith('/offline-analytics') ? '返回分析批次与建议来源' : '返回实践会话与提交历史' }}</RouterLink></div>
    </section>

    <section v-if="showEditor" class="workspace-panel workspace-editor learning-editor" aria-label="任务编辑器">
      <div class="panel-title-row"><h2>{{ editingTask ? '编辑任务' : '创建任务' }}</h2><button class="text-command" type="button" @click="closeEditor">关闭</button></div>
      <LearningTaskEditor :key="editingTask?.id ?? 'new-task'" :initial-value="editingTask" :plans="planOptions" :projects="projectOptions" :submitting="learningStore.saving" @submit="saveTask" @cancel="closeEditor" />
    </section>

    <div class="learning-toolbar">
      <LiquidTabs :model-value="scope" :options="scopeOptions" ariaLabel="任务范围" @update:model-value="changeScope" />
      <div class="learning-task-ratio"><strong>{{ completedCount }}</strong><span>/ {{ learningStore.taskPage.items.length }} 本页已完成</span></div>
    </div>

    <div v-if="learningStore.taskError" class="inline-alert is-error" role="alert"><span>{{ learningStore.taskError }}</span><button type="button" @click="loadTasks">重试</button></div>
    <div v-if="learningStore.loadingTasks" class="workspace-list-loading"><span v-for="index in 5" :key="index" /></div>
    <ul v-else-if="learningStore.taskPage.items.length" class="workspace-task-board learning-task-board">
      <li v-for="task in learningStore.taskPage.items" :key="task.id" :class="{ 'is-completed': task.status === 'completed' }">
        <div class="task-priority" :data-priority="task.priority"><span />{{ priorityLabels[task.priority] }}</div>
        <div class="task-main-copy"><strong>{{ task.title }}</strong><p v-if="task.description">{{ task.description }}</p><small>{{ task.scheduled_date }} · {{ task.plan?.name || '独立任务' }} · {{ task.project?.name || '无关联项目' }}</small><div><RouterLink v-for="link in sourceLinks(task.description)" :key="link" :to="link">{{ link.startsWith('/offline-analytics') ? '分析建议来源' : '实践提交历史' }}</RouterLink></div></div>
        <span class="status-chip">{{ taskStatusLabels[task.status] }}</span>
        <div class="learning-row-actions">
          <button class="text-command" type="button" @click="openEditor(task)">编辑</button>
          <button v-if="task.status === 'pending' || task.status === 'in_progress'" class="secondary-command compact-command" type="button" :disabled="learningStore.actionKey === `task:${task.id}`" @click="completeTask(task)">完成</button>
          <button class="text-command danger-text-command" type="button" :disabled="learningStore.actionKey === `task:${task.id}`" @click="removeTask(task)">删除</button>
        </div>
      </li>
    </ul>
    <section v-else class="empty-state"><h2>{{ scope === 'today' ? '今天还没有任务' : '还没有学习任务' }}</h2><p>从计划中拆出一项今天可以完成的行动。</p><button class="primary-command" type="button" @click="openEditor()">创建任务</button></section>

    <nav v-if="learningStore.taskPage.total_pages > 1" class="pagination" aria-label="任务分页">
      <button type="button" :disabled="pageNumber <= 1 || learningStore.loadingTasks" @click="changePage(pageNumber - 1)">上一页</button><span>第 {{ pageNumber }} / {{ learningStore.taskPage.total_pages }} 页</span><button type="button" :disabled="pageNumber >= learningStore.taskPage.total_pages || learningStore.loadingTasks" @click="changePage(pageNumber + 1)">下一页</button>
    </nav>
  </div>
</template>
