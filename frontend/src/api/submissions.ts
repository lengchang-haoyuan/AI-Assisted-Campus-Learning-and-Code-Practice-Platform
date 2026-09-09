import { apiClient } from './client'
import type {
  FeedbackDecision,
  FeedbackResponse,
  NotificationPageResponse,
  NotificationResponse,
  PendingAssignmentPageResponse,
  SubmissionCreateInput,
  SubmissionPageResponse,
  SubmissionResponse,
  SubmissionVersionPageResponse,
} from '@/types/submission'

export async function submitAssignment(
  assignmentId: number,
  input: SubmissionCreateInput,
): Promise<SubmissionResponse> {
  return (await apiClient.post<SubmissionResponse>(`/campus/assignments/${assignmentId}/submissions`, input)).data
}

export async function listAssignmentSubmissions(assignmentId: number): Promise<SubmissionPageResponse> {
  return (await apiClient.get<SubmissionPageResponse>(`/campus/assignments/${assignmentId}/submissions`, {
    params: { page: 1, page_size: 100 },
  })).data
}

export async function listSubmissions(page = 1, pendingOnly = false): Promise<SubmissionPageResponse> {
  return (await apiClient.get<SubmissionPageResponse>('/campus/submissions', {
    params: { page, page_size: 20, pending_only: pendingOnly },
  })).data
}

export async function listPendingAssignments(page = 1): Promise<PendingAssignmentPageResponse> {
  return (await apiClient.get<PendingAssignmentPageResponse>('/campus/submissions/pending-assignments', {
    params: { page, page_size: 20 },
  })).data
}

export async function getSubmission(submissionId: number): Promise<SubmissionResponse> {
  return (await apiClient.get<SubmissionResponse>(`/campus/submissions/${submissionId}`)).data
}

export async function listSubmissionVersions(submissionId: number, page = 1): Promise<SubmissionVersionPageResponse> {
  return (await apiClient.get<SubmissionVersionPageResponse>(`/campus/submissions/${submissionId}/versions`, {
    params: { page, page_size: 20 },
  })).data
}

export async function createFeedback(
  submissionId: number,
  versionNumber: number,
  expectedRevision: number,
  decision: FeedbackDecision,
  comment: string,
): Promise<FeedbackResponse> {
  return (await apiClient.post<FeedbackResponse>(
    `/campus/submissions/${submissionId}/versions/${versionNumber}/feedback`,
    { expected_revision: expectedRevision, decision, comment },
  )).data
}

export async function detachProjectReference(submissionId: number, versionNumber: number): Promise<void> {
  await apiClient.delete(`/campus/submissions/${submissionId}/versions/${versionNumber}/project-reference`)
}

export async function listNotifications(page = 1, unreadOnly = false): Promise<NotificationPageResponse> {
  return (await apiClient.get<NotificationPageResponse>('/notifications', {
    params: { page, page_size: 20, unread_only: unreadOnly },
  })).data
}

export async function markNotificationRead(notificationId: number): Promise<NotificationResponse> {
  return (await apiClient.post<NotificationResponse>(`/notifications/${notificationId}/read`)).data
}
