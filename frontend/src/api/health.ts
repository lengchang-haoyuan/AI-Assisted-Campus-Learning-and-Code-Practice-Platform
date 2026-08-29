import { apiClient } from './client'
import type { HealthResponse } from '@/types/health'

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/health', { signal })
  return response.data
}

