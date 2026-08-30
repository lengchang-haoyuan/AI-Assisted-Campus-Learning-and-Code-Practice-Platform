import { apiClient } from './client'
import type { UserResponse } from '@/types/user'

export async function getCurrentUser(): Promise<UserResponse> {
  const response = await apiClient.get<UserResponse>('/users/me')
  return response.data
}
