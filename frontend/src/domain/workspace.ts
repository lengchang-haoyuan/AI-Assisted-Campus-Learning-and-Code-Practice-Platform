import type { RecordType, TaskPriority, TaskStatus } from '@/types/workspace'

export const priorityLabels: Record<TaskPriority, string> = {
  low: '低优先级',
  medium: '普通',
  high: '高优先级',
}

export const taskStatusLabels: Record<TaskStatus, string> = {
  pending: '待完成',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

export const recordTypeLabels: Record<RecordType, string> = {
  study: '自主学习',
  project: '项目实践',
  workflow: '工作流',
  ai: 'AI 辅助',
  course: '课程学习',
  task: '任务复盘',
}

export function getLocalDateValue(value = new Date()): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatWorkspaceDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    hour: value.includes('T') ? '2-digit' : undefined,
    minute: value.includes('T') ? '2-digit' : undefined,
  }).format(parsed)
}
