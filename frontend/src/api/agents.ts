import { apiClient } from './client'
import type {
  AgentRecordResponse,
  ProjectAnalysisInput,
  PromptAgentInput,
} from '@/types/ai'

const AGENT_TIMEOUT_MS = 620_000

export async function runProjectAnalysis(
  projectId: number,
  input: ProjectAnalysisInput,
): Promise<AgentRecordResponse> {
  const response = await apiClient.post<AgentRecordResponse>(
    '/agents/project-analysis',
    { project_id: projectId, input },
    { timeout: AGENT_TIMEOUT_MS },
  )
  return response.data
}

export async function runPromptAgent(
  projectId: number,
  input: PromptAgentInput,
): Promise<AgentRecordResponse> {
  const response = await apiClient.post<AgentRecordResponse>(
    '/agents/prompt',
    { project_id: projectId, input },
    { timeout: AGENT_TIMEOUT_MS },
  )
  return response.data
}

export async function getAgentResult(
  requestId: number,
  signal?: AbortSignal,
): Promise<AgentRecordResponse> {
  const response = await apiClient.get<AgentRecordResponse>(`/agents/results/${requestId}`, { signal })
  return response.data
}
