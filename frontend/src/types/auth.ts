import type { UserResponse } from './user'

export interface RegisterInput {
  username: string
  email: string
  password: string
  invite_token?: string
}

export interface LoginInput {
  identifier: string
  password: string
  slider_token: string
}

export interface SliderChallenge {
  challenge_id: string
  expires_in: number
}

export interface SliderVerification {
  slider_token: string
  expires_in: number
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export type RegisterResponse = UserResponse
