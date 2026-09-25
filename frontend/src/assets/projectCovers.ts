import aiWorkflowCover from './projects/ai-workflow-cover.webp'
import cCover from './projects/c-cover.webp'
import generalCover from './projects/general-cover.webp'
import javaCover from './projects/java-cover.webp'
import pythonCover from './projects/python-cover.webp'
import vueCover from './projects/vue-cover.webp'

interface ProjectCoverSource {
  name?: string | null
  language?: string | null
  framework?: string | null
  frontend?: string | null
  backend?: string | null
}

const AI_TERMS = [
  '人工智能',
  '大模型',
  '机器学习',
  '工作流',
  '智能体',
  'agent',
  'deepseek',
  'openai',
  'workflow',
  'machine learning',
  'llm',
]

function normalize(value: string | null | undefined): string {
  return value?.trim().toLowerCase() ?? ''
}

function includesAny(value: string, terms: readonly string[]): boolean {
  return terms.some((term) => value.includes(term))
}

export function getProjectCover(project: ProjectCoverSource): string {
  const fields = [
    project.name,
    project.language,
    project.framework,
    project.frontend,
    project.backend,
  ].map(normalize)
  const searchableText = fields.join(' ')
  const language = normalize(project.language)
  const framework = normalize(project.framework)
  const frontend = normalize(project.frontend)
  const backend = normalize(project.backend)

  if (includesAny(searchableText, AI_TERMS) || /(^|[^a-z])ai([^a-z]|$)/u.test(searchableText)) {
    return aiWorkflowCover
  }
  if ([language, framework, frontend].some((value) => includesAny(value, ['vue', 'nuxt']))) {
    return vueCover
  }
  if (language.includes('python') || [framework, backend].some((value) => includesAny(value, ['fastapi', 'django', 'flask']))) {
    return pythonCover
  }
  if ((language.includes('java') && !language.includes('javascript')) || [framework, backend].some((value) => includesAny(value, ['spring', 'mybatis']))) {
    return javaCover
  }
  if (/^(c|c\+\+|cpp|c(89|90|99|11|17|18|23))$/u.test(language) || searchableText.includes('c语言')) {
    return cCover
  }
  return generalCover
}
