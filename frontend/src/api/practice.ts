import { apiClient } from './client'
import { PRACTICE_TEMPLATE } from '@/domain/practice'
import type { PracticeAction, PracticeSession, PracticeSubmission } from '@/types/practice'

export async function listPracticeSessions(projectId: number, page: number, signal?: AbortSignal): Promise<PracticeSession[]> {
  return (await apiClient.get<PracticeSession[]>(`/projects/${projectId}/practice-sessions`, { params: { offset: (page - 1) * 20, limit: 20 }, signal })).data
}
export async function getPracticeSession(id: string, signal?: AbortSignal): Promise<PracticeSession> {
  return (await apiClient.get<PracticeSession>(`/practice-sessions/${id}`, { signal })).data
}
export async function createPracticeSession(projectId: number, version: number, requestKey: string): Promise<PracticeSession> {
  return (await apiClient.post<PracticeSession>(`/projects/${projectId}/practice-sessions`, {
    template_id: PRACTICE_TEMPLATE.id, template_version: PRACTICE_TEMPLATE.version,
    expected_context_version: version, request_key: requestKey,
  })).data
}
export async function submitPracticeAttempt(id: string, payload: PracticeSubmission): Promise<PracticeSession> {
  return (await apiClient.post<PracticeSession>(`/practice-sessions/${id}/attempts`, payload)).data
}
export async function performPracticeAction(id: string, action: PracticeAction, revision: number, key: string, attemptId?: string): Promise<PracticeSession> {
  return (await apiClient.post<PracticeSession>(`/practice-sessions/${id}/actions`, {
    action, expected_revision: revision, request_key: key, ...(attemptId ? { attempt_id: attemptId } : {}),
  }, { timeout: 180_000 })).data
}
