import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'
import { createPracticeSession, getPracticeSession, listPracticeSessions, performPracticeAction, submitPracticeAttempt } from '@/api/practice'
import { getProject } from '@/api/projects'
import { findProjectContext } from '@/api/workflowContext'
import { getApiErrorMessage } from '@/api/errors'
import { MODEL_ACTIONS, PRACTICE_TEMPLATE } from '@/domain/practice'
import { useAuthStore } from '@/stores/auth'
import type { PracticeAction, PracticeSession, PracticeSubmission } from '@/types/practice'
import type { ProjectResponse } from '@/types/project'
import type { ProjectContextResponse } from '@/types/ai'

export function usePracticeWorkbench() {
  const auth = useAuthStore()
  const project = shallowRef<ProjectResponse | null>(null)
  const context = shallowRef<ProjectContextResponse | null>(null)
  const session = shallowRef<PracticeSession | null>(null)
  const history = shallowRef<PracticeSession[]>([])
  const page = ref(1)
  const loading = ref(false)
  const localBusy = ref(false)
  const modelBusy = ref(false)
  const error = ref<string | null>(null)
  const notice = ref<string | null>(null)
  const selectedAttemptId = ref<string | null>(null)
  const selectedAttempt = computed(() => session.value?.attempts.find(item => item.id === selectedAttemptId.value) ?? session.value?.current_attempt ?? null)
  const selectedCurrent = computed(() => selectedAttempt.value?.id === session.value?.current_attempt?.id)
  let generation = 0
  let modelTicket = 0
  let controller: AbortController | null = null
  let poll: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  const valid = (epoch: number, token: string | null) => !disposed && generation === epoch && auth.token === token
  function accept(value: PracticeSession): void {
    if (value.project_id !== project.value?.id || value.owner_user_id !== auth.currentUser?.id) throw new Error('返回的实践不属于当前项目或账号。')
    if (value.template_id !== PRACTICE_TEMPLATE.id || value.template_version !== PRACTICE_TEMPLATE.version) throw new Error('该历史模板暂不支持操作，请保留原记录。')
    if (session.value?.id === value.id && value.revision < session.value.revision) return
    const previous = session.value?.current_attempt?.id
    session.value = value
    if (!selectedAttemptId.value || !value.attempts.some(item => item.id === selectedAttemptId.value) || selectedAttemptId.value === previous) {
      selectedAttemptId.value = value.current_attempt?.id ?? null
    }
    history.value = history.value.map(item => item.id === value.id ? value : item)
  }
  async function load(projectId: number, sessionId?: string): Promise<void> {
    const epoch = ++generation, token = auth.token
    ++modelTicket
    controller?.abort(); clearTimeout(poll)
    controller = new AbortController()
    project.value = null; context.value = null; session.value = null; history.value = []
    selectedAttemptId.value = null; error.value = null; notice.value = null
    modelBusy.value = localBusy.value = false; page.value = 1
    loading.value = true
    try {
      if (!Number.isSafeInteger(projectId) || projectId < 1) throw new Error('项目地址无效。')
      const [item, snapshot, sessions] = await Promise.all([getProject(projectId), findProjectContext(projectId, controller.signal), listPracticeSessions(projectId, 1, controller.signal)])
      if (!valid(epoch, token)) return
      project.value = item; context.value = snapshot; history.value = sessions
      const selected = sessionId ?? sessions[0]?.id
      if (selected) {
        const detail = await getPracticeSession(selected, controller.signal)
        if (valid(epoch, token)) accept(detail)
      }
    } catch (cause: unknown) {
      if (valid(epoch, token) && !controller.signal.aborted) error.value = getApiErrorMessage(cause, '实践加载失败，请检查权限后重试。')
    } finally { if (valid(epoch, token)) loading.value = false }
  }
  async function refresh(): Promise<void> {
    const item = session.value
    if (!item) return
    const epoch = generation, token = auth.token
    try {
      const value = await getPracticeSession(item.id)
      if (valid(epoch, token) && session.value?.id === item.id) accept(value)
    } catch (cause: unknown) {
      if (valid(epoch, token)) error.value = getApiErrorMessage(cause, '查询未完成，请再次刷新。')
    }
  }
  function schedulePoll(): void {
    clearTimeout(poll)
    const epoch = generation
    poll = setTimeout(async () => {
      if (disposed || generation !== epoch) return
      await refresh()
      if (generation === epoch && (modelBusy.value || session.value?.status === 'running')) schedulePoll()
    }, 1200)
  }
  async function create(): Promise<PracticeSession | null> {
    if (!project.value || !context.value || context.value.is_stale || localBusy.value || modelBusy.value) return null
    const epoch = generation, token = auth.token, projectId = project.value.id
    localBusy.value = true; error.value = null
    try {
      const value = await createPracticeSession(projectId, context.value.version, crypto.randomUUID())
      if (!valid(epoch, token)) return null
      accept(value); history.value = [value, ...history.value]; notice.value = '实践已创建，尚未请求 AI。'
      return value
    } catch (cause: unknown) {
      if (valid(epoch, token)) error.value = getApiErrorMessage(cause, '创建未完成，请先刷新会话列表确认是否已创建。')
      return null
    } finally { if (valid(epoch, token)) localBusy.value = false }
  }
  async function action(kind: PracticeAction): Promise<void> {
    const item = session.value
    const isModel = MODEL_ACTIONS.includes(kind)
    if (!item || localBusy.value || (modelBusy.value && kind !== 'cancel' && kind !== 'resume')) return
    if ((isModel || kind === 'confirm') && item.current_attempt && !selectedCurrent.value) return
    const epoch = generation, token = auth.token
    const ticket = isModel ? ++modelTicket : modelTicket
    if (isModel) modelBusy.value = true
    else localBusy.value = true
    error.value = null; notice.value = null
    if (isModel) schedulePoll()
    try {
      const attemptId = item.current_step_key === 'implement' ? item.current_attempt?.id : undefined
      const value = await performPracticeAction(item.id, kind, item.revision, crypto.randomUUID(), attemptId)
      if (valid(epoch, token) && session.value?.id === item.id && (!isModel || ticket === modelTicket)) {
        accept(value)
        if (kind === 'cancel' || kind === 'resume') {
          ++modelTicket; modelBusy.value = false; clearTimeout(poll)
        }
        notice.value = kind === 'confirm' && value.status === 'completed' ? '本次实践已结束，记录的是本人审阅。' : '操作已保存。'
      }
    } catch (cause: unknown) {
      if (valid(epoch, token) && (!isModel || ticket === modelTicket)) {
        error.value = getApiErrorMessage(cause, '请求未完成；请先刷新已有记录，再明确决定下一动作。')
        await refresh()
      }
    } finally {
      if (valid(epoch, token) && (!isModel || ticket === modelTicket)) {
        if (isModel) modelBusy.value = false
        else localBusy.value = false
        if (session.value?.status === 'running') schedulePoll()
      }
    }
  }
  async function submit(payload: Omit<PracticeSubmission, 'expected_revision' | 'request_key' | 'step_key'>): Promise<boolean> {
    const item = session.value
    if (!item || localBusy.value || modelBusy.value) return false
    const epoch = generation, token = auth.token
    localBusy.value = true; error.value = null; notice.value = null
    try {
      const value = await submitPracticeAttempt(item.id, { ...payload, expected_revision: item.revision, request_key: crypto.randomUUID(), step_key: 'implement' })
      if (!valid(epoch, token) || session.value?.id !== item.id) return false
      accept(value); selectedAttemptId.value = value.current_attempt?.id ?? null
      notice.value = '新版本已保存，可直接审阅结束，也可按需请求建议。'
      return true
    } catch (cause: unknown) {
      if (valid(epoch, token)) { error.value = getApiErrorMessage(cause, '提交未完成，草稿保留；请刷新当前版本后核对。'); await refresh() }
      return false
    } finally { if (valid(epoch, token)) localBusy.value = false }
  }
  async function historyPage(next: number): Promise<void> {
    if (!project.value || loading.value || localBusy.value || modelBusy.value) return
    const epoch = generation, token = auth.token
    loading.value = true
    try {
      const values = await listPracticeSessions(project.value.id, next)
      if (valid(epoch, token)) { history.value = values; page.value = next }
    } catch (cause: unknown) { if (valid(epoch, token)) error.value = getApiErrorMessage(cause, '历史加载失败。') }
    finally { if (valid(epoch, token)) loading.value = false }
  }
  onBeforeUnmount(() => { disposed = true; ++generation; controller?.abort(); clearTimeout(poll) })
  return { project, context, session, history, page, loading, localBusy, modelBusy, error, notice, selectedAttemptId, selectedAttempt, selectedCurrent, load, refresh, create, action, submit, historyPage }
}
