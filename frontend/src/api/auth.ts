import { apiClient } from './client'
import type {
  LoginInput,
  RegisterInput,
  RegisterResponse,
  TokenResponse,
} from '@/types/auth'

export async function register(input: RegisterInput): Promise<RegisterResponse> {
  const response = await apiClient.post<RegisterResponse>('/auth/register', input)
  return response.data
}

export async function login(input: LoginInput): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', input)
  return response.data
}
