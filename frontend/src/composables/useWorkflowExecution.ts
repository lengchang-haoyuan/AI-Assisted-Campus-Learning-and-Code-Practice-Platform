import { computed, onUnmounted, ref, shallowRef } from 'vue'
import { listWorkflowRuns, runWorkflow } from '@/api/workflows'
import { prepareWorkflowContext } from '@/api/workflowContext'
import { getApiErrorMessage } from '@/api/errors'
import type { WorkflowRunMode, WorkflowRunResponse } from '@/types/workflow'

export function useWorkflowExecution(workflowId: number) {
  const runs = shallowRef<WorkflowRunResponse[]>([])
  const selectedId = ref<number | null>(null)
  const page = ref(1)
  const totalPages = ref(0)
  const loading = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  const active = computed(() => runs.value.some(run => run.status === 'running' || run.status === 'pending'))
  const busy = computed(() => submitting.value || active.value)
  const selected = computed(() => runs.value.find(run => run.id === selectedId.value) ?? runs.value[0] ?? null)
  let disposed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  let sequence = 0

  function stopPolling(): void { clearTimeout(timer); timer = undefined }

  async function refresh(nextPage = page.value): Promise<void> {
    stopPolling()
    const requestSequence = ++sequence
    loading.value = true
    try {
      const result = await listWorkflowRuns(workflowId, nextPage)
      if (disposed || requestSequence !== sequence) return
      runs.value = result.items
      page.value = result.page
      totalPages.value = result.total_pages
      if (submitting.value || !result.items.some(run => run.id === selectedId.value)) selectedId.value = result.items[0]?.id ?? null
      error.value = null
      if (active.value || submitting.value) timer = setTimeout(() => { void refresh(1) }, 1800)
    } catch (cause: unknown) {
      if (!disposed && requestSequence === sequence) error.value = getApiErrorMessage(cause, '运行记录加载失败，请刷新重试')
    } finally {
      if (!disposed && requestSequence === sequence) loading.value = false
    }
  }

  async function start(projectId: number, version: number, mode: WorkflowRunMode): Promise<boolean> {
    if (busy.value || loading.value) return false
    submitting.value = true
    error.value = null
    stopPolling()
    try {
      await prepareWorkflowContext(projectId)
      if (disposed) return false
      timer = setTimeout(() => { void refresh(1) }, 1200)
      const result = await runWorkflow(workflowId, version, mode)
      if (disposed) return false
      ++sequence
      runs.value = [result, ...runs.value.filter(run => run.id !== result.id)]
      selectedId.value = result.id
      return true
    } catch (cause: unknown) {
      if (!disposed) error.value = getApiErrorMessage(cause, '运行请求未完成，请先刷新运行记录确认状态')
      return false
    } finally {
      submitting.value = false
      stopPolling()
      // 请求中断不等于服务端停止；保留记录供用户确认，避免自动重复生成。
      if (!disposed) {
        const requestError = error.value
        await refresh(1)
        if (requestError) error.value = requestError
      }
    }
  }

  onUnmounted(() => { disposed = true; ++sequence; stopPolling() })
  return { runs, selectedId, selected, page, totalPages, loading, submitting, busy, error, refresh, start }
}
