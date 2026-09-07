import { apiClient } from './client'
import type {
  AccountResponse,
  AccountUpdateInput,
  AuditResponse,
  CampusMeResponse,
  InvitationCreateInput,
  InvitationIssuedResponse,
  InvitationResponse,
  MembershipResponse,
  PageResponse,
} from '@/types/campus'

export async function getCampusMe(): Promise<CampusMeResponse> {
  return (await apiClient.get<CampusMeResponse>('/campus/me')).data
}

export async function redeemInvitation(token: string): Promise<MembershipResponse> {
  return (await apiClient.post<MembershipResponse>('/campus/invitations/redeem', { token })).data
}

export async function createInvitation(input: InvitationCreateInput): Promise<InvitationIssuedResponse> {
  return (await apiClient.post<InvitationIssuedResponse>('/campus/invitations', input)).data
}

export async function getAccounts(query = ''): Promise<PageResponse<AccountResponse>> {
  return (await apiClient.get<PageResponse<AccountResponse>>('/campus/admin/accounts', {
    params: { query: query || undefined, page: 1, page_size: 100 },
  })).data
}

export async function updateAccount(userId: number, input: AccountUpdateInput): Promise<AccountResponse> {
  return (await apiClient.patch<AccountResponse>(`/campus/admin/accounts/${userId}`, input)).data
}

export async function getInvitations(): Promise<PageResponse<InvitationResponse>> {
  return (await apiClient.get<PageResponse<InvitationResponse>>('/campus/admin/invitations', {
    params: { page: 1, page_size: 100 },
  })).data
}

export async function revokeInvitation(invitationId: number, reason: string): Promise<void> {
  await apiClient.post(`/campus/admin/invitations/${invitationId}/revoke`, { reason })
}

export async function issuePasswordReset(userId: number, reason: string): Promise<{ token: string; expires_at: string }> {
  return (await apiClient.post<{ token: string; expires_at: string }>(
    `/campus/admin/accounts/${userId}/password-resets`, { reason },
  )).data
}

export async function getAudits(): Promise<PageResponse<AuditResponse>> {
  return (await apiClient.get<PageResponse<AuditResponse>>('/campus/admin/audits', {
    params: { page: 1, page_size: 100 },
  })).data
}
