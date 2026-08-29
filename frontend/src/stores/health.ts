import axios from 'axios'
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getHealth } from '@/api/health'
import type { HealthResponse } from '@/types/health'

export const useHealthStore = defineStore('health', () => {
  const data = ref<HealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let activeController: AbortController | null = null

  async function fetchHealth(): Promise<void> {
    activeController?.abort()
    const controller = new AbortController()
    activeController = controller
    loading.value = true
    error.value = null

    try {
      data.value = await getHealth(controller.signal)
    } catch (requestError: unknown) {
      if (axios.isCancel(requestError)) {
        return
      }
      data.value = null
      error.value = axios.isAxiosError(requestError)
        ? '无法连接后端服务，请确认 FastAPI 已在 8000 端口启动。'
        : '服务状态检查失败，请稍后重试。'
    } finally {
      if (activeController === controller) {
        activeController = null
        loading.value = false
      }
    }
  }

  function cancel(): void {
    activeController?.abort()
    activeController = null
    loading.value = false
  }

  return { data, loading, error, fetchHealth, cancel }
})

