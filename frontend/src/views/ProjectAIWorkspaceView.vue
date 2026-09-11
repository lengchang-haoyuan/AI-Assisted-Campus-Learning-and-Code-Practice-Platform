<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getAgentResult, runProjectAnalysis, runPromptAgent } from '@/api/agents'
import { getApiErrorMessage, getApiErrorStatus } from '@/api/errors'
import { getProject } from '@/api/projects'
import {
  createProjectContext,
  findProjectContext,
  updateProjectContext,
} from '@/api/workflowContext'
import AgentResultPanel from '@/components/AgentResultPanel.vue'
import type {
  AgentRecordResponse,
  ProjectContextPatch,
  ProjectContextResponse,
  ProjectContextValues,
  PromptAgentInput,
} from '@/types/ai'
import type { ProjectResponse } from '@/types/project'
import type { JsonObject, JsonValue } from '@/types/workflow'
import '@/styles/ai-workspace.css'

type AITool = 'analysis' | 'prompt'

interface ContextDraft {
  projectName: string
  difficulty: ProjectContextValues['difficulty']
  language: string
  framework: string
  frontend: string
  backend: string
  database: string
  outputRequirement: string
  features: string
  constraints: string
  requirements: string
  architecture: string
  extensions: string
}

const route = useRoute()
const projectId = Number(route.params.id)
const project = ref<ProjectResponse | null>(null)
const context = ref<ProjectContextResponse | null>(null)
const draft = ref<ContextDraft | null>(null)
const loading = ref(true)
const contextSaving = ref(false)
const contextError = ref<string | null>(null)
const contextNotice = ref<string | null>(null)
const activeTool = ref<AITool>('analysis')
const analysisFocus = ref('')
const analysisRequirements = ref('')
const promptForm = ref<PromptAgentInput>({
  task: '根据当前项目上下文生成可执行的开发提示词',
  environment: '本地开发环境',
  target_directory: '.',
  input_description: '当前 ProjectContext 与本表单的补充说明',
  output_description: '可直接交给开发 Agent 的实施提示词和验收标准',
  coding_standards: [
    '安全性优先，其次是正确性和可读性',
    '使用明确类型并运行相关测试',
  ],
  api_requirements: [],
  frontend_backend_relationship: null,
})
const codingStandardsText = ref(promptForm.value.coding_standards.join('\n'))
const apiRequirementsText = ref('')
const agentRecord = ref<AgentRecordResponse | null>(null)
const requestIdInput = ref('')
const agentBusy = ref(false)
const agentError = ref<string | null>(null)
let mounted = true
let resultController: AbortController | null = null

const contextReady = computed(() => context.value !== null && !context.value.is_stale)
const resultUsesOldContext = computed(() => (
  agentRecord.value !== null &&
  context.value !== null &&
  agentRecord.value.context_version !== context.value.version
))
const contextMetadata = computed(() => {
  if (!context.value) return []
  return Object.entries(context.value.field_metadata).sort(([left], [right]) => left.localeCompare(right))
})

const fieldLabels: Record<string, string> = {
  project_name: '项目名称',
  difficulty: '难度',
  language: '语言',
  framework: '框架',
  frontend: '前端',
  backend: '后端',
  database: '数据库',
  requirements: '项目需求',
  output_requirement: '交付要求',
  architecture: '架构',
  features: '功能',
  constraints: '约束',
  extensions: '扩展信息',
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function sourceLabel(source: ProjectContextResponse['source']): string {
  if (source.type === 'project') return `项目 #${source.id}`
  if (source.type === 'user') return `用户 #${source.id}`
  return `工作流节点 ${source.node_key ?? `#${source.id}`}`
}

function makeDraft(values: ProjectContextValues): ContextDraft {
  return {
    projectName: values.project_name,
    difficulty: values.difficulty,
    language: values.language ?? '',
    framework: values.framework ?? '',
    frontend: values.frontend ?? '',
    backend: values.backend ?? '',
    database: values.database ?? '',
    outputRequirement: values.output_requirement ?? '',
    features: values.features.join('\n'),
    constraints: values.constraints.join('\n'),
    requirements: values.requirements ? JSON.stringify(values.requirements, null, 2) : '',
    architecture: values.architecture ? JSON.stringify(values.architecture, null, 2) : '',
    extensions: Object.keys(values.extensions).length ? JSON.stringify(values.extensions, null, 2) : '',
  }
}

function applyContext(value: ProjectContextResponse): void {
  context.value = value
  draft.value = makeDraft(value.values)
}

async function load(): Promise<void> {
  if (!Number.isInteger(projectId) || projectId < 1) {
    loading.value = false
    contextError.value = '项目地址无效。'
    return
  }
  loading.value = true
  contextError.value = null
  try {
    const [projectResponse, contextResponse] = await Promise.all([
      getProject(projectId),
      findProjectContext(projectId),
    ])
    if (!mounted) return
    project.value = projectResponse
    if (contextResponse) applyContext(contextResponse)
    else {
      context.value = null
      draft.value = null
    }
  } catch (error: unknown) {
    if (mounted) contextError.value = getApiErrorMessage(error, 'AI 工作台加载失败，请重试')
  } finally {
    if (mounted) loading.value = false
  }
}

async function createContext(): Promise<void> {
  if (contextSaving.value) return
  contextSaving.value = true
  contextError.value = null
  contextNotice.value = null
  try {
    applyContext(await createProjectContext(projectId))
    contextNotice.value = 'Context 已从当前项目资料创建。此操作没有调用模型。'
  } catch (error: unknown) {
    if (getApiErrorStatus(error) === 409) {
      const latest = await findProjectContext(projectId)
      if (latest) applyContext(latest)
      contextNotice.value = 'Context 已由另一个会话创建，现已载入最新版本。'
    } else {
      contextError.value = getApiErrorMessage(error, 'Context 创建失败，请重试')
    }
  } finally {
    contextSaving.value = false
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return true
  if (Array.isArray(value)) return value.every(isJsonValue)
  return isJsonObject(value)
}

function isJsonObject(value: unknown): value is JsonObject {
  return isRecord(value) && Object.values(value).every(isJsonValue)
}

function parseJsonObject(text: string, label: string): JsonObject | null {
  if (!text.trim()) return null
  const parsed: unknown = JSON.parse(text)
  if (!isJsonObject(parsed)) {
    throw new Error(`${label}必须是 JSON 对象`)
  }
  return parsed
}

function parseRequirements(text: string): JsonObject[] | null {
  if (!text.trim()) return null
  const parsed: unknown = JSON.parse(text)
  if (!Array.isArray(parsed) || !parsed.every(isJsonObject)) {
    throw new Error('项目需求必须是 JSON 对象数组')
  }
  if (parsed.length > 100) throw new Error('项目需求不能超过 100 项')
  return parsed
}

function parseLines(value: string, label: string, maximum = 100): string[] {
  const items = [...new Set(value.split('\n').map((item) => item.trim()).filter(Boolean))]
  if (items.length > maximum) throw new Error(`${label}不能超过 ${maximum} 项`)
  if (items.some((item) => item.length > 500)) throw new Error(`${label}单项不能超过 500 个字符`)
  return items
}

function nullableText(value: string): string | null {
  return value.trim() || null
}

function buildContextValues(): ProjectContextValues {
  if (!draft.value) throw new Error('Context 尚未载入')
  const projectName = draft.value.projectName.trim()
  if (!projectName) throw new Error('项目名称不能为空')
  return {
    project_name: projectName,
    difficulty: draft.value.difficulty,
    language: nullableText(draft.value.language),
    framework: nullableText(draft.value.framework),
    frontend: nullableText(draft.value.frontend),
    backend: nullableText(draft.value.backend),
    database: nullableText(draft.value.database),
    output_requirement: nullableText(draft.value.outputRequirement),
    features: parseLines(draft.value.features, '功能'),
    constraints: parseLines(draft.value.constraints, '约束'),
    requirements: parseRequirements(draft.value.requirements),
    architecture: parseJsonObject(draft.value.architecture, '架构'),
    extensions: parseJsonObject(draft.value.extensions, '扩展信息') ?? {},
  }
}

async function saveContext(): Promise<void> {
  if (!context.value || contextSaving.value) return
  contextError.value = null
  contextNotice.value = null
  let values: ProjectContextValues
  try {
    values = buildContextValues()
  } catch (error: unknown) {
    contextError.value = error instanceof Error ? error.message : 'Context 输入格式无效'
    return
  }
  contextSaving.value = true
  try {
    const response = await updateProjectContext(projectId, context.value.version, values)
    applyContext(response.context)
    contextNotice.value = response.changed_fields.length
      ? `Context 已保存为 v${response.context.version}，${response.stale_node_ids.length} 个节点需要重新运行。`
      : '内容没有变化，Context 版本保持不变。'
  } catch (error: unknown) {
    if (getApiErrorStatus(error) === 409) {
      contextError.value = 'Context 版本已变化。你的草稿仍保留，请先载入最新版本后再合并修改。'
    } else {
      contextError.value = getApiErrorMessage(error, 'Context 保存失败，请检查输入后重试')
    }
  } finally {
    contextSaving.value = false
  }
}

async function reloadContext(): Promise<void> {
  if (contextSaving.value) return
  contextSaving.value = true
  contextError.value = null
  try {
    const latest = await findProjectContext(projectId)
    if (!latest) {
      context.value = null
      draft.value = null
      return
    }
    applyContext(latest)
    contextNotice.value = `已载入 Context v${latest.version}。`
  } catch (error: unknown) {
    contextError.value = getApiErrorMessage(error, 'Context 刷新失败，请重试')
  } finally {
    contextSaving.value = false
  }
}

function projectValuePatch(source: ProjectResponse, staleFields: string[]): ProjectContextPatch {
  const values: ProjectContextPatch = {}
  for (const field of staleFields) {
    if (field === 'project_name') values.project_name = source.name
    else if (field === 'difficulty') values.difficulty = source.difficulty
    else if (field === 'language') values.language = source.language
    else if (field === 'framework') values.framework = source.framework
    else if (field === 'frontend') values.frontend = source.frontend
    else if (field === 'backend') values.backend = source.backend
    else if (field === 'database') values.database = source.database
    else if (field === 'requirements') values.requirements = source.requirements
    else if (field === 'output_requirement') values.output_requirement = source.output_requirement
  }
  return values
}

async function syncProjectChanges(): Promise<void> {
  if (!context.value || !context.value.stale_fields.length || contextSaving.value) return
  contextSaving.value = true
  contextError.value = null
  contextNotice.value = null
  try {
    const latestProject = await getProject(projectId)
    const response = await updateProjectContext(
      projectId,
      context.value.version,
      projectValuePatch(latestProject, context.value.stale_fields),
    )
    project.value = latestProject
    applyContext(response.context)
    contextNotice.value = `已同步项目字段并保存为 Context v${response.context.version}。此操作没有调用模型。`
  } catch (error: unknown) {
    contextError.value = getApiErrorStatus(error) === 409
      ? 'Context 版本已变化，请载入最新版本后再同步。'
      : getApiErrorMessage(error, '项目资料同步失败，请重试')
  } finally {
    contextSaving.value = false
  }
}

function requireReadyContext(): boolean {
  if (contextReady.value) return true
  agentError.value = context.value
    ? 'Context 与项目资料不一致，请先同步后再运行 AI。'
    : '请先创建项目 Context。'
  return false
}

async function runAnalysis(): Promise<void> {
  if (agentBusy.value || !requireReadyContext()) return
  let additionalRequirements: string[]
  try {
    additionalRequirements = parseLines(analysisRequirements.value, '补充需求', 10)
  } catch (error: unknown) {
    agentError.value = error instanceof Error ? error.message : '补充需求格式无效'
    return
  }
  agentBusy.value = true
  agentError.value = null
  try {
    const result = await runProjectAnalysis(projectId, {
      focus: nullableText(analysisFocus.value),
      additional_requirements: additionalRequirements,
    })
    if (!mounted) return
    agentRecord.value = result
    requestIdInput.value = String(result.request_id)
  } catch (error: unknown) {
    if (mounted) agentError.value = `${getApiErrorMessage(error, '需求分析未完成')}。请先查询已有结果，再明确选择是否重试。`
  } finally {
    if (mounted) agentBusy.value = false
  }
}

function validatePromptInput(): PromptAgentInput | null {
  const requiredFields: Array<[string, string]> = [
    [promptForm.value.task, '开发任务'],
    [promptForm.value.environment, '运行环境'],
    [promptForm.value.target_directory, '目标目录'],
    [promptForm.value.input_description, '输入说明'],
    [promptForm.value.output_description, '输出说明'],
  ]
  const missing = requiredFields.find(([value]) => !value.trim())
  if (missing) {
    agentError.value = `${missing[1]}不能为空`
    return null
  }
  if (promptForm.value.target_directory.startsWith('/') || promptForm.value.target_directory.startsWith('\\') || promptForm.value.target_directory.includes(':') || promptForm.value.target_directory.split(/[\\/]/).includes('..')) {
    agentError.value = '目标目录必须是项目内相对路径'
    return null
  }
  try {
    const codingStandards = parseLines(codingStandardsText.value, '编码规范', 10)
    const apiRequirements = parseLines(apiRequirementsText.value, 'API 要求', 10)
    if (!codingStandards.length) throw new Error('至少填写一条编码规范')
    if ([...codingStandards, ...apiRequirements].some((item) => item.length > 200)) throw new Error('编码规范或 API 要求单项不能超过 200 个字符')
    return {
      ...promptForm.value,
      task: promptForm.value.task.trim(),
      environment: promptForm.value.environment.trim(),
      target_directory: promptForm.value.target_directory.trim().replaceAll('\\', '/'),
      input_description: promptForm.value.input_description.trim(),
      output_description: promptForm.value.output_description.trim(),
      coding_standards: codingStandards,
      api_requirements: apiRequirements,
      frontend_backend_relationship: nullableText(promptForm.value.frontend_backend_relationship ?? ''),
    }
  } catch (error: unknown) {
    agentError.value = error instanceof Error ? error.message : 'Prompt 输入格式无效'
    return null
  }
}

async function runPrompt(): Promise<void> {
  if (agentBusy.value || !requireReadyContext()) return
  const input = validatePromptInput()
  if (!input) return
  agentBusy.value = true
  agentError.value = null
  try {
    const result = await runPromptAgent(projectId, input)
    if (!mounted) return
    agentRecord.value = result
    requestIdInput.value = String(result.request_id)
  } catch (error: unknown) {
    if (mounted) agentError.value = `${getApiErrorMessage(error, '开发 Prompt 未完成')}。请先查询已有结果，再明确选择是否重试。`
  } finally {
    if (mounted) agentBusy.value = false
  }
}

async function queryResult(): Promise<void> {
  const requestId = Number(requestIdInput.value)
  if (!Number.isInteger(requestId) || requestId < 1 || agentBusy.value) {
    agentError.value = '请输入有效的结果编号'
    return
  }
  resultController?.abort()
  resultController = new AbortController()
  agentBusy.value = true
  agentError.value = null
  try {
    const result = await getAgentResult(requestId, resultController.signal)
    if (mounted) agentRecord.value = result
  } catch (error: unknown) {
    if (mounted && resultController?.signal.aborted !== true) {
      agentError.value = getApiErrorMessage(error, '结果查询失败，请检查编号后重试')
    }
  } finally {
    if (mounted) agentBusy.value = false
  }
}

onMounted(() => { void load() })
onBeforeUnmount(() => {
  mounted = false
  resultController?.abort()
})
</script>

<template>
  <section class="page-shell ai-workspace-page">
    <RouterLink class="back-link" :to="project ? `/projects/${project.id}` : '/projects'">返回项目详情</RouterLink>

    <div v-if="loading" class="ai-workspace-loading" aria-label="AI 工作台加载中"><span /><span /><span /></div>
    <div v-else-if="contextError && !project" class="state-panel state-panel--error">
      <strong>AI 工作台加载失败</strong><p>{{ contextError }}</p><button class="secondary-command" type="button" @click="load">重试</button>
    </div>

    <template v-else-if="project">
      <header class="page-header ai-workspace-header">
        <div>
          <p class="page-kicker">Project AI Workspace</p>
          <h1>{{ project.name }} · AI 工作台</h1>
          <p>先维护可追踪的项目 Context，再主动运行需求分析、开发 Prompt 或关联工作流。</p>
        </div>
        <RouterLink class="secondary-command" to="/workflows">打开工作流</RouterLink>
      </header>

      <section class="ai-context-panel" aria-labelledby="context-title">
        <header class="ai-section-heading">
          <div><span>STEP 01</span><h2 id="context-title">项目 Context</h2><p>保存使用版本校验。更新 Context 会标记受影响节点，但不会自动调用模型。</p></div>
          <div v-if="context" class="ai-context-version"><strong>v{{ context.version }}</strong><span>{{ formatTime(context.updated_at) }}</span></div>
        </header>

        <div v-if="contextError" class="inline-alert is-error" role="alert">
          <span>{{ contextError }}</span>
          <button v-if="context" type="button" @click="reloadContext">载入最新版本</button>
        </div>
        <div v-if="contextNotice" class="inline-alert is-success" role="status">{{ contextNotice }}</div>

        <div v-if="!context" class="ai-context-empty">
          <strong>这个项目还没有 Context</strong>
          <p>创建后会从当前项目名称、技术栈、需求和交付要求生成 v1。</p>
          <button class="primary-command" type="button" :disabled="contextSaving" @click="createContext">{{ contextSaving ? '正在创建…' : '创建项目 Context' }}</button>
        </div>

        <template v-else-if="draft">
          <div v-if="context.is_stale" class="ai-stale-banner" role="alert">
            <div><strong>Context 与项目资料不一致</strong><p>待同步字段：{{ context.stale_fields.map((field) => fieldLabels[field] ?? field).join('、') }}。同步前不能运行 AI。</p></div>
            <button class="primary-command" type="button" :disabled="contextSaving" @click="syncProjectChanges">同步项目变更</button>
          </div>
          <div v-if="context.stale_node_ids.length" class="ai-node-impact">
            <strong>需要重新生成的节点</strong>
            <span v-for="nodeId in context.stale_node_ids" :key="nodeId" class="tech-tag">节点 #{{ nodeId }}</span>
          </div>

          <form class="ai-context-form" @submit.prevent="saveContext">
            <label class="field field-span-2"><span>项目名称</span><input v-model="draft.projectName" maxlength="120" required /></label>
            <label class="field"><span>难度</span><select v-model="draft.difficulty"><option value="beginner">入门</option><option value="intermediate">进阶</option><option value="advanced">高级</option></select></label>
            <label class="field"><span>主要语言</span><input v-model="draft.language" maxlength="100" placeholder="例如 Python" /></label>
            <label class="field"><span>核心框架</span><input v-model="draft.framework" maxlength="100" placeholder="例如 FastAPI" /></label>
            <label class="field"><span>前端</span><input v-model="draft.frontend" maxlength="100" placeholder="例如 Vue 3" /></label>
            <label class="field"><span>后端</span><input v-model="draft.backend" maxlength="100" placeholder="例如 FastAPI" /></label>
            <label class="field"><span>数据库</span><input v-model="draft.database" maxlength="100" placeholder="例如 MySQL" /></label>
            <label class="field field-span-2"><span>交付要求</span><textarea v-model="draft.outputRequirement" maxlength="5000" /></label>
            <label class="field"><span>核心功能</span><textarea v-model="draft.features" placeholder="每行一项，最多 100 项" /></label>
            <label class="field"><span>项目约束</span><textarea v-model="draft.constraints" placeholder="每行一项，最多 100 项" /></label>
            <label class="field field-span-2"><span>项目需求 JSON</span><textarea v-model="draft.requirements" class="code-textarea" spellcheck="false" placeholder='[{"title":"需求名称"}]' /></label>
            <label class="field"><span>架构 JSON</span><textarea v-model="draft.architecture" class="code-textarea" spellcheck="false" placeholder='{"style":"modular"}' /></label>
            <label class="field"><span>扩展信息 JSON</span><textarea v-model="draft.extensions" class="code-textarea" spellcheck="false" placeholder="{}" /></label>
            <div class="form-actions field-span-2">
              <button class="secondary-command" type="button" :disabled="contextSaving" @click="reloadContext">放弃草稿并刷新</button>
              <button class="primary-command" type="submit" :disabled="contextSaving">{{ contextSaving ? '正在保存…' : `保存 Context v${context.version}` }}</button>
            </div>
          </form>

          <details class="ai-context-metadata">
            <summary>查看字段来源与版本</summary>
            <div class="ai-metadata-grid">
              <article v-for="([field, metadata]) in contextMetadata" :key="field">
                <strong>{{ fieldLabels[field] ?? field }}</strong>
                <span>v{{ metadata.version }} · {{ sourceLabel(metadata.source) }}</span>
                <small>{{ formatTime(metadata.updated_at) }}</small>
              </article>
            </div>
          </details>
        </template>
      </section>

      <section class="ai-agent-panel" aria-labelledby="agent-title">
        <header class="ai-section-heading">
          <div><span>STEP 02</span><h2 id="agent-title">AI 操作</h2><p>调用使用当前 Context 版本。失败或网络中断后不会自动重试。</p></div>
          <span class="status-chip" :data-status="contextReady ? 'completed' : 'stale'">{{ contextReady ? 'Context 可用' : '请先处理 Context' }}</span>
        </header>

        <div class="liquid-tabs" role="tablist" aria-label="AI 工具">
          <button class="liquid-tabs__item" :class="{ 'is-active': activeTool === 'analysis' }" type="button" role="tab" :aria-selected="activeTool === 'analysis'" @click="activeTool = 'analysis'">需求分析</button>
          <button class="liquid-tabs__item" :class="{ 'is-active': activeTool === 'prompt' }" type="button" role="tab" :aria-selected="activeTool === 'prompt'" @click="activeTool = 'prompt'">开发 Prompt</button>
        </div>

        <form v-if="activeTool === 'analysis'" class="ai-agent-form" @submit.prevent="runAnalysis">
          <label class="field field-span-2"><span>分析重点（可选）</span><textarea v-model="analysisFocus" maxlength="1000" placeholder="例如：认证边界、数据隔离和验收标准" /></label>
          <label class="field field-span-2"><span>补充需求（可选）</span><textarea v-model="analysisRequirements" placeholder="每行一项，最多 10 项" /></label>
          <button class="primary-command field-span-2" type="submit" :disabled="agentBusy || !contextReady">{{ agentBusy ? '模型调用中…' : '运行需求分析' }}</button>
        </form>

        <form v-else class="ai-agent-form" @submit.prevent="runPrompt">
          <label class="field field-span-2"><span>开发任务</span><textarea v-model="promptForm.task" maxlength="1000" required /></label>
          <label class="field"><span>运行环境</span><input v-model="promptForm.environment" maxlength="500" required /></label>
          <label class="field"><span>项目内目标目录</span><input v-model="promptForm.target_directory" maxlength="300" required /></label>
          <label class="field"><span>输入说明</span><textarea v-model="promptForm.input_description" maxlength="500" required /></label>
          <label class="field"><span>输出说明</span><textarea v-model="promptForm.output_description" maxlength="500" required /></label>
          <label class="field"><span>编码规范</span><textarea v-model="codingStandardsText" placeholder="每行一项，1-10 项" required /></label>
          <label class="field"><span>API 要求</span><textarea v-model="apiRequirementsText" placeholder="每行一项，最多 10 项" /></label>
          <label class="field field-span-2"><span>前后端关系（可选）</span><textarea v-model="promptForm.frontend_backend_relationship" maxlength="800" /></label>
          <button class="primary-command field-span-2" type="submit" :disabled="agentBusy || !contextReady">{{ agentBusy ? '模型调用中…' : '生成开发 Prompt' }}</button>
        </form>

        <p v-if="agentBusy" class="ai-agent-running" role="status">正在等待模型响应。关闭页面只会停止本页等待，不代表服务端调用已取消。</p>
        <p v-if="agentError" class="inline-alert is-error" role="alert">{{ agentError }}</p>

        <form class="ai-result-query" @submit.prevent="queryResult">
          <label class="field"><span>按结果编号查询</span><input v-model="requestIdInput" type="number" min="1" step="1" inputmode="numeric" placeholder="例如 128" /></label>
          <button class="secondary-command" type="submit" :disabled="agentBusy">刷新结果</button>
          <small>查询只返回当前账号有权读取的记录。</small>
        </form>
      </section>

      <p v-if="resultUsesOldContext" class="inline-alert ai-result-stale" role="status">当前结果使用 Context v{{ agentRecord?.context_version }}，最新版本是 v{{ context?.version }}。如需更新，请由你主动重新生成。</p>
      <AgentResultPanel :record="agentRecord" />
    </template>
  </section>
</template>
