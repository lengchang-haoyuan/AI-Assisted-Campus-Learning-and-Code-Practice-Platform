import research from './campus-studio/research.webp'
import notebook from './campus-studio/notebook.webp'
import noticeboard from './campus-studio/noticeboard.webp'
import books from './campus-studio/books.webp'
import components from './campus-studio/components.webp'
import researchSmall from './campus-studio/research-400.webp'
import notebookSmall from './campus-studio/notebook-400.webp'
import noticeboardSmall from './campus-studio/noticeboard-400.webp'
import booksSmall from './campus-studio/books-400.webp'
import componentsSmall from './campus-studio/components-400.webp'

interface ProjectCoverSource {
  name?: string | null
  language?: string | null
  framework?: string | null
  frontend?: string | null
  backend?: string | null
}

interface ProjectCoverAsset {
  src: string
  small: string
  width: number
}

const covers = {
  research: { src: research, small: researchSmall, width: 800 },
  notebook: { src: notebook, small: notebookSmall, width: 800 },
  noticeboard: { src: noticeboard, small: noticeboardSmall, width: 1200 },
  books: { src: books, small: booksSmall, width: 800 },
  components: { src: components, small: componentsSmall, width: 800 },
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

function selectProjectCover(project: ProjectCoverSource): ProjectCoverAsset {
  const [name, language, framework, frontend, backend] = [
    project.name,
    project.language,
    project.framework,
    project.frontend,
    project.backend,
  ].map(normalize)
  const searchableText = [name, language, framework, frontend, backend].join(' ')

  if (includesAny(name, ['失物', 'lost and found'])) return covers.noticeboard
  if (includesAny(name, ['图书', 'library'])) return covers.books

  if (includesAny(searchableText, AI_TERMS) || /(^|[^a-z])ai([^a-z]|$)/u.test(searchableText)) {
    return covers.research
  }
  if ([language, framework, frontend].some((value) => includesAny(value, ['vue', 'nuxt']))) {
    return covers.components
  }
  if (language.includes('python') || [framework, backend].some((value) => includesAny(value, ['fastapi', 'django', 'flask']))) {
    return covers.research
  }
  if ((language.includes('java') && !language.includes('javascript')) || [framework, backend].some((value) => includesAny(value, ['spring', 'mybatis']))) {
    return covers.books
  }
  if (/^(c|c\+\+|cpp|c(89|90|99|11|17|18|23))$/u.test(language) || searchableText.includes('c语言')) {
    return covers.notebook
  }
  return covers.noticeboard
}

export function getProjectCover(project: ProjectCoverSource): string {
  return selectProjectCover(project).src
}

export function getProjectCoverSrcset(project: ProjectCoverSource): string {
  const { src, small, width } = selectProjectCover(project)
  return `${small} 400w, ${src} ${width}w`
}
