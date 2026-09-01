import type { CourseStatus, LearningPlanStatus } from '@/types/learning'

export const courseStatusLabels: Record<CourseStatus, string> = {
  active: '进行中',
  completed: '已结课',
  archived: '已归档',
}

export const planStatusLabels: Record<LearningPlanStatus, string> = {
  draft: '草稿',
  active: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

export function toLocalDateTimeInput(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}
