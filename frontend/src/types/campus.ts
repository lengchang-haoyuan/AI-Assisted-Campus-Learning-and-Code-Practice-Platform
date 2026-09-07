export type CampusRole = 'student' | 'teacher' | 'administrator'
export type MembershipStatus = 'active' | 'suspended' | 'revoked'
export type InvitationStatus = 'pending' | 'consumed' | 'revoked' | 'expired'

export interface MembershipResponse {
  id: number
  role: CampusRole
  status: MembershipStatus
  revision: number
  verified_at: string
}

export interface CampusMeResponse {
  membership: MembershipResponse | null
}

export interface InvitationResponse {
  id: number
  target_user_id: number | null
  target_email: string | null
  role: CampusRole
  status: InvitationStatus
  expires_at: string
  created_at: string
}

export interface InvitationIssuedResponse extends InvitationResponse {
  token: string
}

export interface AccountResponse {
  user_id: number
  username: string
  email: string
  account_enabled: boolean
  auth_version: number
  membership: MembershipResponse | null
}

export interface AuditResponse {
  id: number
  actor_user_id: number
  target_user_id: number | null
  action: string
  outcome: string
  reason: string | null
  occurred_at: string
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface InvitationCreateInput {
  target_user_id?: number
  target_email?: string
  role: Exclude<CampusRole, 'administrator'>
  expires_in_hours: number
  reason: string
}

export interface AccountUpdateInput {
  reason: string
  expected_revision?: number
  expected_auth_version?: number
  role?: CampusRole
  campus_status?: MembershipStatus
  account_enabled?: boolean
}
