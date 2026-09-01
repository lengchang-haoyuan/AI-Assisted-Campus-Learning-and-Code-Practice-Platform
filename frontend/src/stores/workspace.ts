import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/api/errors'
import {
  completeTask as completeTaskRequest,
  createLearningRecord as createLearningRecordRequest,
  createTask as createTaskRequest,
  getWorkspaceDashboard,
  getWorkspaceProject,
  listLearningRecords,
  listTasks,
  listWorkspaceProjects,
} from '@/api/workspace'
import type {
  LearningRecordCreateInput,
  LearningRecordListResponse,
  PageQuery,
  TaskCreateInput,
  TaskListResponse,
  TaskResponse,
  WorkspaceDashboardResponse,
  WorkspaceProjectDetailResponse,
  WorkspaceProjectListResponse,
} from '@/types/workspace'

const EMPTY_TASK_PAGE: TaskListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}
const EMPTY_RECORD_PAGE: LearningRecordListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}
const EMPTY_PROJECT_PAGE: WorkspaceProjectListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const dashboard = ref<WorkspaceDashboardResponse | null>(null)
  const taskPage = ref<TaskListResponse>({ ...EMPTY_TASK_PAGE })
  const recordPage = ref<LearningRecordListResponse>({ ...EMPTY_RECORD_PAGE })
  const projectPage = ref<WorkspaceProjectListResponse>({ ...EMPTY_PROJECT_PAGE })
  const projectDetail = ref<WorkspaceProjectDetailResponse | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const actionTaskId = ref<number | null>(null)
  const error = ref<string | null>(null)
  let requestSequence = 0

  async function runLoad<T>(request: () => Promise<T>, apply: (value: T) => void): Promise<void> {
    const sequence = ++requestSequence
    loading.value = true
    error.value = null
    try {
      const result = await request()
      if (sequence === requestSequence) apply(result)
    } catch (caught: unknown) {
      if (sequence === requestSequence) {
        error.value = getApiErrorMessage(caught, '工作台数据加载失败，请重试')
      }
      throw caught
    } finally {
      if (sequence === requestSequence) loading.value = false
    }
  }

  async function fetchDashboard(selectedDate: string, utcOffsetMinutes: number): Promise<void> {
    return runLoad(
      () => getWorkspaceDashboard(selectedDate, utcOffsetMinutes),
      (result) => { dashboard.value = result },
    )
  }

  async function fetchTasks(query: PageQuery, selectedDate?: string): Promise<void> {
    return runLoad(
      () => listTasks(query, selectedDate),
      (result) => { taskPage.value = result },
    )
  }

  async function fetchRecords(query: PageQuery): Promise<void> {
    return runLoad(
      () => listLearningRecords(query),
      (result) => { recordPage.value = result },
    )
  }

  async function fetchProjects(query: PageQuery): Promise<void> {
    return runLoad(
      () => listWorkspaceProjects(query),
      (result) => { projectPage.value = result },
    )
  }

  async function fetchProject(projectId: number): Promise<void> {
    return runLoad(
      () => getWorkspaceProject(projectId),
      (result) => { projectDetail.value = result },
    )
  }

  async function createTask(input: TaskCreateInput): Promise<TaskResponse> {
    saving.value = true
    try {
      return await createTaskRequest(input)
    } finally {
      saving.value = false
    }
  }

  async function createRecord(input: LearningRecordCreateInput): Promise<void> {
    saving.value = true
    try {
      await createLearningRecordRequest(input)
    } finally {
      saving.value = false
    }
  }

  function replaceTask(task: TaskResponse): void {
    taskPage.value = {
      ...taskPage.value,
      items: taskPage.value.items.map((item) => item.id === task.id ? task : item),
    }
    if (dashboard.value) {
      dashboard.value = {
        ...dashboard.value,
        today_tasks: dashboard.value.today_tasks.map((item) => item.id === task.id ? task : item),
      }
    }
    if (projectDetail.value) {
      projectDetail.value = {
        ...projectDetail.value,
        recent_tasks: projectDetail.value.recent_tasks.map(
          (item) => item.id === task.id ? task : item,
        ),
      }
    }
  }

  async function completeTask(taskId: number): Promise<void> {
    actionTaskId.value = taskId
    try {
      replaceTask(await completeTaskRequest(taskId))
    } finally {
      actionTaskId.value = null
    }
  }

  return {
    dashboard,
    taskPage,
    recordPage,
    projectPage,
    projectDetail,
    loading,
    saving,
    actionTaskId,
    error,
    fetchDashboard,
    fetchTasks,
    fetchRecords,
    fetchProjects,
    fetchProject,
    createTask,
    createRecord,
    completeTask,
  }
})
