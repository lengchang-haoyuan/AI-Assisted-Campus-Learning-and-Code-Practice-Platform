import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getApiErrorMessage } from '@/api/errors'
import {
  createWorkflow as createWorkflowRequest,
  deleteWorkflow as deleteWorkflowRequest,
  getWorkflowGraph,
  listWorkflows,
  saveWorkflowGraph,
  updateWorkflow as updateWorkflowRequest,
} from '@/api/workflows'
import type {
  WorkflowCreateInput,
  WorkflowGraphResponse,
  WorkflowGraphUpdateInput,
  WorkflowListQuery,
  WorkflowListResponse,
  WorkflowResponse,
  WorkflowUpdateInput,
} from '@/types/workflow'

const EMPTY_PAGE: WorkflowListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
}

export const useWorkflowStore = defineStore('workflows', () => {
  const page = ref<WorkflowListResponse>({ ...EMPTY_PAGE })
  const currentGraph = ref<WorkflowGraphResponse | null>(null)
  const listLoading = ref(false)
  const graphLoading = ref(false)
  const saving = ref(false)
  const actionKey = ref<string | null>(null)
  const listError = ref<string | null>(null)
  const graphError = ref<string | null>(null)
  let listRequestSequence = 0
  let graphRequestSequence = 0

  async function fetchWorkflows(query: WorkflowListQuery): Promise<void> {
    const sequence = ++listRequestSequence
    listLoading.value = true
    listError.value = null
    try {
      const result = await listWorkflows(query)
      if (sequence === listRequestSequence) page.value = result
    } catch (error: unknown) {
      if (sequence === listRequestSequence) {
        listError.value = getApiErrorMessage(error, '工作流列表加载失败，请重试')
      }
      throw error
    } finally {
      if (sequence === listRequestSequence) listLoading.value = false
    }
  }

  async function fetchGraph(workflowId: number): Promise<WorkflowGraphResponse> {
    const sequence = ++graphRequestSequence
    graphLoading.value = true
    graphError.value = null
    try {
      const result = await getWorkflowGraph(workflowId)
      if (sequence === graphRequestSequence) currentGraph.value = result
      return result
    } catch (error: unknown) {
      if (sequence === graphRequestSequence) {
        currentGraph.value = null
        graphError.value = getApiErrorMessage(error, '工作流加载失败，请重试')
      }
      throw error
    } finally {
      if (sequence === graphRequestSequence) graphLoading.value = false
    }
  }

  async function createWorkflow(input: WorkflowCreateInput): Promise<WorkflowResponse> {
    saving.value = true
    try {
      return await createWorkflowRequest(input)
    } finally {
      saving.value = false
    }
  }

  async function updateWorkflow(
    workflowId: number,
    input: WorkflowUpdateInput,
  ): Promise<WorkflowResponse> {
    saving.value = true
    try {
      const result = await updateWorkflowRequest(workflowId, input)
      if (currentGraph.value?.workflow.id === workflowId) {
        currentGraph.value = { ...currentGraph.value, workflow: result }
      }
      return result
    } finally {
      saving.value = false
    }
  }

  async function saveGraph(
    workflowId: number,
    input: WorkflowGraphUpdateInput,
  ): Promise<WorkflowGraphResponse> {
    saving.value = true
    try {
      const result = await saveWorkflowGraph(workflowId, input)
      currentGraph.value = result
      return result
    } finally {
      saving.value = false
    }
  }

  async function deleteWorkflow(workflowId: number): Promise<void> {
    actionKey.value = `workflow:${workflowId}`
    try {
      await deleteWorkflowRequest(workflowId)
      page.value = {
        ...page.value,
        items: page.value.items.filter((workflow) => workflow.id !== workflowId),
        total: Math.max(0, page.value.total - 1),
      }
      if (currentGraph.value?.workflow.id === workflowId) currentGraph.value = null
    } finally {
      actionKey.value = null
    }
  }

  function clearCurrentGraph(): void {
    currentGraph.value = null
    graphError.value = null
  }

  return {
    page,
    currentGraph,
    listLoading,
    graphLoading,
    saving,
    actionKey,
    listError,
    graphError,
    fetchWorkflows,
    fetchGraph,
    createWorkflow,
    updateWorkflow,
    saveGraph,
    deleteWorkflow,
    clearCurrentGraph,
  }
})
