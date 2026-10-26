import type { PracticeAction, PracticeSession, PracticeStatus, PracticeGuidance } from '@/types/practice'
import type { JsonObject } from '@/types/workflow'

export const PRACTICE_TEMPLATE = { id: 'python-learning-csv', version: '1.0', title: 'Python CSV 学习记录清洗', signature: 'summarize_records(csv_text: str) -> dict' } as const
export const PRACTICE_STATUS: Record<PracticeStatus, string> = {
  ready: '等待阅读任务', running: '正在请求 AI', waiting_submission: '等待提交代码',
  waiting_revision: '等待本人审阅', waiting_confirmation: '等待本人审阅', failed: 'AI 请求未完成',
  cancelled: '已取消，可恢复', completed: '本次实践已结束',
}
export const MODEL_ACTIONS: PracticeAction[] = ['start', 'hint', 'explain', 'review', 'continue']
export function canSubmit(session: PracticeSession): boolean {
  return session.current_step_key === 'implement' && ['waiting_submission', 'waiting_revision', 'waiting_confirmation', 'failed'].includes(session.status)
}
export function availableActions(session: PracticeSession): PracticeAction[] {
  if (session.status === 'completed') return []
  if (session.status === 'cancelled') return ['resume']
  if (session.status === 'running') return ['cancel', 'resume']
  const actions: PracticeAction[] = ['cancel']
  if (session.status === 'ready') return ['start', ...actions]
  if (session.status === 'failed') actions.push('resume', 'continue')
  else actions.push('hint', 'explain')
  if (session.current_step_key === 'understand' && session.status === 'waiting_confirmation') actions.push('confirm')
  if (session.current_step_key === 'implement') {
    if (!session.current_attempt) return actions.filter(action => action !== 'explain')
    if (session.current_attempt.can_confirm) actions.push('confirm')
    if (!session.current_attempt.feedback.ai_static_review && session.status !== 'failed') actions.push('review')
  }
  return actions
}
export function isGuidance(value: unknown): value is PracticeGuidance {
  if (!value || typeof value !== 'object') return false
  return 'summary' in value && typeof value.summary === 'string' && 'guidance' in value && Array.isArray(value.guidance)
    && value.guidance.every(item => typeof item === 'string') && 'checks' in value && Array.isArray(value.checks)
    && value.checks.every(item => typeof item === 'string')
}
export function parseSubmission(code: string, text: string): JsonObject {
  if (!code.trim() || code.length > 12000) throw new Error('请填写非空代码，最多 12000 个字符。')
  const value: unknown = text.trim() ? JSON.parse(text) : {}
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error('声明输出须为 JSON 对象，也可以留空。')
  if (new TextEncoder().encode(JSON.stringify(value)).length > 8192) throw new Error('声明输出不能超过 8 KiB。')
  return value as JsonObject
}
