import type { ProjectDifficulty, ProjectResponse, ProjectStatus } from '@/types/project'

export const difficultyLabels: Record<ProjectDifficulty, string> = {
  beginner: '入门',
  intermediate: '进阶',
  advanced: '挑战',
}

export const statusLabels: Record<ProjectStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  published: '已发布',
  archived: '已归档',
}

export function getProjectStack(project: ProjectResponse): string[] {
  return [
    project.language,
    project.framework,
    project.frontend,
    project.backend,
    project.database,
  ].filter((value): value is string => Boolean(value))
}

export function formatProjectTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatRequirement(requirement: Record<string, unknown>): string {
  const firstValue = Object.values(requirement)[0]
  if (typeof firstValue === 'string') return firstValue
  if (typeof firstValue === 'number' || typeof firstValue === 'boolean') {
    return String(firstValue)
  }
  return JSON.stringify(requirement)
}
