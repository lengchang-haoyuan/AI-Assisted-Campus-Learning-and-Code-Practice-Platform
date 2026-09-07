import { apiClient } from './client'
import type {
  WorkflowCreateInput,
  WorkflowEdgeCreateInput,
  WorkflowEdgeResponse,
  WorkflowEdgeUpdateInput,
  WorkflowGraphResponse,
  WorkflowGraphUpdateInput,
  WorkflowListQuery,
  WorkflowListResponse,
  WorkflowNodeCreateInput,
  WorkflowNodeResponse,
  WorkflowNodeUpdateInput,
  WorkflowResponse,
  WorkflowUpdateInput,
  WorkflowRunMode,
  WorkflowRunResponse,
  WorkflowRunListResponse,
} from '@/types/workflow'

export async function runWorkflow(workflowId: number, version: number, mode: WorkflowRunMode): Promise<WorkflowRunResponse> {
  const response = await apiClient.post<WorkflowRunResponse>(`/workflows/${workflowId}/run`,
    { expected_version: version, mode }, { timeout: 620_000 })
  return response.data
}

export async function listWorkflowRuns(workflowId: number, page = 1): Promise<WorkflowRunListResponse> {
  const response = await apiClient.get<WorkflowRunListResponse>(`/workflows/${workflowId}/runs`,
    { params: { page, page_size: 10 } })
  return response.data
}

export async function listWorkflows(query: WorkflowListQuery): Promise<WorkflowListResponse> {
  const response = await apiClient.get<WorkflowListResponse>('/workflows', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      project_id: query.projectId,
    },
  })
  return response.data
}

export async function createWorkflow(input: WorkflowCreateInput): Promise<WorkflowResponse> {
  const response = await apiClient.post<WorkflowResponse>('/workflows', input)
  return response.data
}

export async function getWorkflow(workflowId: number): Promise<WorkflowResponse> {
  const response = await apiClient.get<WorkflowResponse>(`/workflows/${workflowId}`)
  return response.data
}

export async function updateWorkflow(
  workflowId: number,
  input: WorkflowUpdateInput,
): Promise<WorkflowResponse> {
  const response = await apiClient.put<WorkflowResponse>(`/workflows/${workflowId}`, input)
  return response.data
}

export async function deleteWorkflow(workflowId: number): Promise<void> {
  await apiClient.delete(`/workflows/${workflowId}`)
}

export async function getWorkflowGraph(workflowId: number): Promise<WorkflowGraphResponse> {
  const response = await apiClient.get<WorkflowGraphResponse>(`/workflows/${workflowId}/graph`)
  return response.data
}

export async function saveWorkflowGraph(
  workflowId: number,
  input: WorkflowGraphUpdateInput,
): Promise<WorkflowGraphResponse> {
  const response = await apiClient.put<WorkflowGraphResponse>(
    `/workflows/${workflowId}/graph`,
    input,
  )
  return response.data
}

export async function createWorkflowNode(
  workflowId: number,
  input: WorkflowNodeCreateInput,
): Promise<WorkflowNodeResponse> {
  const response = await apiClient.post<WorkflowNodeResponse>(
    `/workflows/${workflowId}/nodes`,
    input,
  )
  return response.data
}

export async function updateWorkflowNode(
  workflowId: number,
  nodeId: number,
  input: WorkflowNodeUpdateInput,
): Promise<WorkflowNodeResponse> {
  const response = await apiClient.put<WorkflowNodeResponse>(
    `/workflows/${workflowId}/nodes/${nodeId}`,
    input,
  )
  return response.data
}

export async function deleteWorkflowNode(workflowId: number, nodeId: number): Promise<void> {
  await apiClient.delete(`/workflows/${workflowId}/nodes/${nodeId}`)
}

export async function createWorkflowEdge(
  workflowId: number,
  input: WorkflowEdgeCreateInput,
): Promise<WorkflowEdgeResponse> {
  const response = await apiClient.post<WorkflowEdgeResponse>(
    `/workflows/${workflowId}/edges`,
    input,
  )
  return response.data
}

export async function updateWorkflowEdge(
  workflowId: number,
  edgeId: number,
  input: WorkflowEdgeUpdateInput,
): Promise<WorkflowEdgeResponse> {
  const response = await apiClient.put<WorkflowEdgeResponse>(
    `/workflows/${workflowId}/edges/${edgeId}`,
    input,
  )
  return response.data
}

export async function deleteWorkflowEdge(workflowId: number, edgeId: number): Promise<void> {
  await apiClient.delete(`/workflows/${workflowId}/edges/${edgeId}`)
}
