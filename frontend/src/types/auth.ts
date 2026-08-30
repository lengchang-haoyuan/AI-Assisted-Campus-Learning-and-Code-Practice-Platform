import type { UserResponse } from './user'

export interface RegisterInput {
  username: string
  email: string
  password: string
}

export interface LoginInput {
  identifier: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export type RegisterResponse = UserResponse
