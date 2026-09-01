import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/api/errors'
import {
  createProject as createProjectRequest,
  deleteProject as deleteProjectRequest,
  getProject as getProjectRequest,
  listProjects as listProjectsRequest,
  updateProject as updateProjectRequest,
} from '@/api/projects'
import type {
  ProjectCreateInput,
  ProjectListQuery,
  ProjectListResponse,
  ProjectResponse,
  ProjectUpdateInput,
} from '@/types/project'

const EMPTY_PAGE: ProjectListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 12,
  total_pages: 0,
}

export const useProjectStore = defineStore('projects', () => {
  const page = ref<ProjectListResponse>({ ...EMPTY_PAGE })
  const currentProject = ref<ProjectResponse | null>(null)
  const listLoading = ref(false)
  const detailLoading = ref(false)
  const saving = ref(false)
  const listError = ref<string | null>(null)
  const detailError = ref<string | null>(null)
  let listRequestSequence = 0
  let detailRequestSequence = 0

  const projects = computed(() => page.value.items)

  async function fetchProjects(query: ProjectListQuery): Promise<void> {
    const requestSequence = ++listRequestSequence
    listLoading.value = true
    listError.value = null
    try {
      const result = await listProjectsRequest(query)
      if (requestSequence === listRequestSequence) page.value = result
    } catch (error: unknown) {
      if (requestSequence === listRequestSequence) {
        listError.value = getApiErrorMessage(error, '项目列表加载失败，请重试')
      }
      throw error
    } finally {
      if (requestSequence === listRequestSequence) listLoading.value = false
    }
  }

  async function fetchProject(projectId: number): Promise<ProjectResponse> {
    const requestSequence = ++detailRequestSequence
    detailLoading.value = true
    detailError.value = null
    try {
      const result = await getProjectRequest(projectId)
      if (requestSequence === detailRequestSequence) currentProject.value = result
      return result
    } catch (error: unknown) {
      if (requestSequence === detailRequestSequence) {
        currentProject.value = null
        detailError.value = getApiErrorMessage(error, '项目详情加载失败，请重试')
      }
      throw error
    } finally {
      if (requestSequence === detailRequestSequence) detailLoading.value = false
    }
  }

  async function createProject(input: ProjectCreateInput): Promise<ProjectResponse> {
    saving.value = true
    try {
      return await createProjectRequest(input)
    } finally {
      saving.value = false
    }
  }

  async function updateProject(
    projectId: number,
    input: ProjectUpdateInput,
  ): Promise<ProjectResponse> {
    saving.value = true
    try {
      const result = await updateProjectRequest(projectId, input)
      currentProject.value = result
      return result
    } finally {
      saving.value = false
    }
  }

  async function deleteProject(projectId: number): Promise<void> {
    saving.value = true
    try {
      await deleteProjectRequest(projectId)
      page.value = {
        ...page.value,
        items: page.value.items.filter((project) => project.id !== projectId),
        total: Math.max(0, page.value.total - 1),
      }
      if (currentProject.value?.id === projectId) currentProject.value = null
    } finally {
      saving.value = false
    }
  }

  function clearCurrentProject(): void {
    currentProject.value = null
    detailError.value = null
  }

  return {
    page,
    projects,
    currentProject,
    listLoading,
    detailLoading,
    saving,
    listError,
    detailError,
    fetchProjects,
    fetchProject,
    createProject,
    updateProject,
    deleteProject,
    clearCurrentProject,
  }
})
