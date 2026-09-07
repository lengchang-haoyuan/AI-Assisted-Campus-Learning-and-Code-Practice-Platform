import { apiClient } from './client'
import type {
  ClassMemberResponse,
  ClassMemberRole,
  ClassMembershipStatus,
  PageResponse,
  TeachingAssignmentCreateInput,
  TeachingAssignmentResponse,
  TeachingAssignmentUpdateInput,
  TeachingClassCreateInput,
  TeachingClassResponse,
  TeachingClassUpdateInput,
} from '@/types/teaching'

export async function listTeachingClasses(page = 1): Promise<PageResponse<TeachingClassResponse>> {
  return (await apiClient.get<PageResponse<TeachingClassResponse>>('/campus/classes', {
    params: { page, page_size: 20 },
  })).data
}

export async function createTeachingClass(input: TeachingClassCreateInput): Promise<TeachingClassResponse> {
  return (await apiClient.post<TeachingClassResponse>('/campus/classes', input)).data
}

export async function getTeachingClass(classId: number): Promise<TeachingClassResponse> {
  return (await apiClient.get<TeachingClassResponse>(`/campus/classes/${classId}`)).data
}

export async function updateTeachingClass(classId: number, input: TeachingClassUpdateInput): Promise<TeachingClassResponse> {
  return (await apiClient.patch<TeachingClassResponse>(`/campus/classes/${classId}`, input)).data
}

export async function listClassMembers(classId: number, page = 1): Promise<PageResponse<ClassMemberResponse>> {
  return (await apiClient.get<PageResponse<ClassMemberResponse>>(`/campus/classes/${classId}/members`, {
    params: { page, page_size: 50 },
  })).data
}

export async function addClassMember(
  classId: number,
  campusMembershipId: number,
  memberRole: ClassMemberRole,
): Promise<ClassMemberResponse> {
  return (await apiClient.post<ClassMemberResponse>(`/campus/classes/${classId}/members`, {
    campus_membership_id: campusMembershipId,
    member_role: memberRole,
  })).data
}

export async function updateClassMember(
  classId: number,
  memberId: number,
  expectedRevision: number,
  status: ClassMembershipStatus,
): Promise<ClassMemberResponse> {
  return (await apiClient.patch<ClassMemberResponse>(`/campus/classes/${classId}/members/${memberId}`, {
    expected_revision: expectedRevision,
    status,
  })).data
}

export async function listTeachingAssignments(classId: number, page = 1): Promise<PageResponse<TeachingAssignmentResponse>> {
  return (await apiClient.get<PageResponse<TeachingAssignmentResponse>>(`/campus/classes/${classId}/assignments`, {
    params: { page, page_size: 20 },
  })).data
}

export async function createTeachingAssignment(
  classId: number,
  input: TeachingAssignmentCreateInput,
): Promise<TeachingAssignmentResponse> {
  return (await apiClient.post<TeachingAssignmentResponse>(`/campus/classes/${classId}/assignments`, input)).data
}

export async function getTeachingAssignment(assignmentId: number): Promise<TeachingAssignmentResponse> {
  return (await apiClient.get<TeachingAssignmentResponse>(`/campus/assignments/${assignmentId}`)).data
}

export async function updateTeachingAssignment(
  assignmentId: number,
  input: TeachingAssignmentUpdateInput,
): Promise<TeachingAssignmentResponse> {
  return (await apiClient.patch<TeachingAssignmentResponse>(`/campus/assignments/${assignmentId}`, input)).data
}

async function transitionAssignment(assignmentId: number, action: 'publish' | 'close' | 'archive', revision: number): Promise<TeachingAssignmentResponse> {
  return (await apiClient.post<TeachingAssignmentResponse>(`/campus/assignments/${assignmentId}/${action}`, {
    expected_revision: revision,
  })).data
}

export const publishTeachingAssignment = (assignmentId: number, revision: number) => transitionAssignment(assignmentId, 'publish', revision)
export const closeTeachingAssignment = (assignmentId: number, revision: number) => transitionAssignment(assignmentId, 'close', revision)
export const archiveTeachingAssignment = (assignmentId: number, revision: number) => transitionAssignment(assignmentId, 'archive', revision)
