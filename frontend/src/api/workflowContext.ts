import axios from 'axios'
import { apiClient } from './client'
import { getProject } from './projects'
import type { JsonObject } from '@/types/workflow'

interface ContextResponse { version: number; stale_fields: string[] }

export async function prepareWorkflowContext(projectId: number): Promise<void> {
  let context: ContextResponse
  try {
    context = (await apiClient.get<ContextResponse>(`/projects/${projectId}/context`)).data
  } catch (error: unknown) {
    if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error
    try {
      await apiClient.post(`/projects/${projectId}/context`)
      return
    } catch (creationError: unknown) {
      if (!axios.isAxiosError(creationError) || creationError.response?.status !== 409) throw creationError
      // 另一个会话可能刚完成初始化，重新读取后继续使用已有上下文。
      context = (await apiClient.get<ContextResponse>(`/projects/${projectId}/context`)).data
    }
  }
  if (context.stale_fields.length === 0) return
  const project = await getProject(projectId)
  const source: JsonObject = {
    project_name: project.name, language: project.language, framework: project.framework,
    frontend: project.frontend, backend: project.backend, database: project.database,
    difficulty: project.difficulty, requirements: project.requirements,
    output_requirement: project.output_requirement,
  }
  const values: JsonObject = {}
  for (const field of context.stale_fields) {
    if (!(field in source)) throw new Error('项目上下文包含无法同步的字段')
    values[field] = source[field]!
  }
  await apiClient.put(`/projects/${projectId}/context`, { expected_version: context.version, values })
}
