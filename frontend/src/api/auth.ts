import { apiClient } from './client'
import type {
  LoginInput,
  RegisterInput,
  RegisterResponse,
  TokenResponse,
  SliderChallenge,
  SliderVerification,
} from '@/types/auth'

export async function register(input: RegisterInput): Promise<RegisterResponse> {
  const response = await apiClient.post<RegisterResponse>('/auth/register', input)
  return response.data
}

export async function login(input: LoginInput): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', input)
  return response.data
}

export async function createSliderChallenge(signal: AbortSignal): Promise<SliderChallenge> {
  const response = await apiClient.post<SliderChallenge>('/auth/slider/challenge', {}, { signal })
  return response.data
}

export async function verifySlider(
  challengeId: string,
  position: number,
  signal: AbortSignal,
): Promise<SliderVerification> {
  const response = await apiClient.post<SliderVerification>('/auth/slider/verify', {
    challenge_id: challengeId,
    position,
  }, { signal })
  return response.data
}
