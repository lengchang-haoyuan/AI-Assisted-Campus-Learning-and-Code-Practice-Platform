import axios from 'axios'

interface ApiErrorDetail {
  code: string
  message: string
  request_id: string
}

interface ApiErrorResponse {
  error: ApiErrorDetail
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!isRecord(value) || !isRecord(value.error)) return false
  return (
    typeof value.error.code === 'string' &&
    typeof value.error.message === 'string' &&
    typeof value.error.request_id === 'string'
  )
}

export function getApiErrorMessage(
  error: unknown,
  fallback = '请求失败，请稍后重试',
): string {
  if (!axios.isAxiosError(error)) return fallback
  if (error.code === 'ECONNABORTED') return '请求超时，请检查服务状态后重试'
  if (!error.response) return '无法连接服务器，请确认后端服务已启动'
  if (isApiErrorResponse(error.response.data)) return error.response.data.error.message
  return fallback
}
