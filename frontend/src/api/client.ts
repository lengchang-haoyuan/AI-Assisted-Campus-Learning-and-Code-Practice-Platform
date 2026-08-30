import axios from 'axios'

import { getAccessToken, handleUnauthorized } from '@/auth/session'

const fallbackBaseUrl = 'http://127.0.0.1:8000/api/v1'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || fallbackBaseUrl,
  timeout: 5000,
  headers: {
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      handleUnauthorized()
    }
    return Promise.reject(error)
  },
)
