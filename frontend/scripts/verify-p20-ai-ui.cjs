// P20 浏览器验收：沿用现有外部 Playwright，API 均为虚构响应，不访问数据库或模型。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4178'
const evidenceDir = path.resolve(__dirname, '../../开发相关文档/测试证据')
const now = '2026-09-11T03:20:00Z'
const fieldNames = [
  'project_name', 'language', 'framework', 'frontend', 'backend', 'database',
  'difficulty', 'requirements', 'output_requirement', 'architecture', 'features',
  'constraints', 'extensions',
]

const project = {
  id: 7,
  name: '校园项目实践平台',
  description: '用于验证 P20 AI 页面闭环的虚构项目。',
  difficulty: 'intermediate',
  language: 'Python',
  framework: 'FastAPI',
  frontend: 'Vue 3',
  backend: 'FastAPI',
  database: 'MySQL',
  requirements: [{ title: '学生从页面使用 AI' }],
  output_requirement: '提供可审查的结构化结果',
  status: 'in_progress',
  owner: { id: 1, username: 'p20_student' },
  tags: [],
  is_published: false,
  published_at: null,
  view_count: 0,
  progress: 45,
  created_at: now,
  updated_at: now,
}

function makeContext(version = 1, overrides = {}) {
  const source = { type: 'project', id: 7, node_key: null }
  return {
    project_id: 7,
    version,
    values: {
      project_name: project.name,
      language: project.language,
      framework: project.framework,
      frontend: project.frontend,
      backend: project.backend,
      database: project.database,
      difficulty: project.difficulty,
      requirements: project.requirements,
      output_requirement: project.output_requirement,
      architecture: { style: '单体分层', modules: ['Web', 'API', 'Data'] },
      features: ['项目 Context', 'AI 需求分析'],
      constraints: ['不执行学生代码'],
      extensions: {},
    },
    field_metadata: Object.fromEntries(fieldNames.map(field => [field, { version, updated_at: now, source }])),
    updated_at: now,
    source,
    is_stale: false,
    stale_fields: [],
    stale_node_ids: [],
    ...overrides,
  }
}

const analysisResult = {
  request_id: 101,
  project_id: 7,
  agent_type: 'project_analysis',
  status: 'completed',
  provider: 'fake',
  model: 'fake-p20-model',
  context_version: 2,
  result: {
    result_type: 'project_analysis',
    summary: '本结果由浏览器验收脚本的虚构 Provider 响应生成，用于检查长文本排版、需求拆解和刷新查询。'.repeat(3),
    requirements_breakdown: [{
      title: '页面操作闭环',
      description: '学生能够创建并修改 Context，主动运行需求分析，再按请求编号查询相同结果。',
      acceptance_criteria: ['不依赖 Swagger', '刷新查询后结构化内容仍可读'],
    }],
    technical_challenges: [{ title: '版本冲突', reason: '并发编辑可能覆盖新版本', mitigation: '使用 expected_version 并保留草稿' }],
    development_steps: [
      { order: 1, title: '准备 Context', action: '创建并检查项目上下文', verification: '显示版本、来源和更新时间' },
      { order: 2, title: '运行 Agent', action: '用户主动提交需求分析', verification: '显示请求编号和结构化结果' },
    ],
    knowledge_points: ['乐观锁', '权限隔离', '结构化输出'],
    technology_recommendations: [{ category: '前端', choice: 'Vue 3', reason: '复用现有应用与类型系统', alternatives: ['保持现有栈'] }],
  },
  error: null,
  usage: { prompt_tokens: 320, completion_tokens: 680, latency_ms: 1650 },
  requested_at: now,
  finished_at: now,
}

const promptResult = {
  ...analysisResult,
  request_id: 102,
  agent_type: 'prompt',
  result: {
    result_type: 'prompt',
    title: '实现项目 Context 页面',
    task: '实现项目 Context 页面',
    language: 'TypeScript',
    framework: 'Vue 3',
    environment: '本地开发环境',
    target_directory: 'frontend/src',
    input_description: 'ProjectContext',
    output_description: '可运行页面',
    coding_standards: ['类型明确', '验证关键状态'],
    database: 'MySQL',
    api_requirements: ['/projects/{id}/context'],
    frontend_backend_relationship: 'Axios 调用现有 FastAPI 接口',
    generated_prompt: '# 开发任务\n\n实现 Context 编辑、冲突恢复和结果展示。\n'.repeat(18),
    acceptance_criteria: ['Context 版本冲突可见', '不渲染任意 HTML'],
    risk_notes: ['真实 Provider 调用需要单独控制费用'],
  },
}

async function main() {
  fs.mkdirSync(evidenceDir, { recursive: true })
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.SCHOLARHUB_BROWSER_PATH,
  })
  const contextBrowser = await browser.newContext({ viewport: { width: 1440, height: 1050 } })
  await contextBrowser.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: baseUrl })
  const page = await contextBrowser.newPage()
  const errors = []
  let context = null
  let conflictNextUpdate = true
  let contextWrites = 0
  let modelCalls = 0
  let resultQueries = 0
  let workflowRuns = 0
  let lastWorkflowRun = null

  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'p20-fake-token'))
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const apiPath = url.pathname
    const method = request.method()
    const respond = (data, status = 200) => route.fulfill({ status, json: data })

    if (apiPath.endsWith('/users/me')) return respond({
      id: 1, username: 'p20_student', email: 'p20@example.com', avatar_url: null,
      bio: null, is_active: true, created_at: now, updated_at: now,
    })
    if (apiPath.endsWith('/campus/me')) return respond({ membership: null })
    if (apiPath.endsWith('/projects/7') && method === 'GET') return respond(project)
    if (apiPath.endsWith('/projects/7/context') && method === 'GET') {
      return context ? respond(context) : respond({ error: { code: 'not_found', message: 'Context 不存在', request_id: 'fake' } }, 404)
    }
    if (apiPath.endsWith('/projects/7/context') && method === 'POST') {
      context = makeContext()
      return respond(context, 201)
    }
    if (apiPath.endsWith('/projects/7/context') && method === 'PUT') {
      contextWrites += 1
      if (conflictNextUpdate) {
        conflictNextUpdate = false
        return respond({ error: { code: 'version_conflict', message: 'Context 版本冲突', request_id: 'fake' } }, 409)
      }
      const input = request.postDataJSON()
      context = makeContext((context?.version || 1) + 1, {
        values: { ...context.values, ...input.values },
        source: { type: 'user', id: 1, node_key: null },
        stale_node_ids: [21],
      })
      return respond({ context, changed_fields: Object.keys(input.values), stale_node_ids: [21] })
    }
    if (apiPath.endsWith('/agents/project-analysis') && method === 'POST') {
      modelCalls += 1
      return respond(analysisResult, 201)
    }
    if (apiPath.endsWith('/agents/prompt') && method === 'POST') {
      modelCalls += 1
      return respond(promptResult, 201)
    }
    if (apiPath.endsWith('/agents/results/101')) { resultQueries += 1; return respond(analysisResult) }
    if (apiPath.endsWith('/agents/results/102')) { resultQueries += 1; return respond(promptResult) }
    if (apiPath.endsWith('/workflows/11/graph')) return respond({
      workflow: { id: 11, project: { id: 7, name: project.name }, name: '项目分析工作流', description: null, status: 'stale', version: 4, node_count: 3, edge_count: 2, created_at: now, updated_at: now },
      nodes: [
        { id: 21, workflow_id: 11, node_key: 'requirements', node_type: 'requirements_analysis', name: '需求分析', position_x: 80, position_y: 120, config: { instruction: '分析需求', expected_output: '' }, status: 'stale', context_version: 1, created_at: now, updated_at: now },
        { id: 22, workflow_id: 11, node_key: 'stack', node_type: 'tech_stack_analysis', name: '技术栈分析', position_x: 380, position_y: 120, config: { instruction: '分析技术栈', expected_output: '' }, status: 'stale', context_version: 1, created_at: now, updated_at: now },
        { id: 23, workflow_id: 11, node_key: 'architecture', node_type: 'architecture_design', name: '架构设计', position_x: 680, position_y: 120, config: { instruction: '设计架构', expected_output: '' }, status: 'stale', context_version: 1, created_at: now, updated_at: now },
      ],
      edges: [
        { id: 31, workflow_id: 11, source_node_id: 21, target_node_id: 22, source_node_key: 'requirements', target_node_key: 'stack', condition_data: null, created_at: now },
        { id: 32, workflow_id: 11, source_node_id: 22, target_node_id: 23, source_node_key: 'stack', target_node_key: 'architecture', condition_data: null, created_at: now },
      ],
    })
    if (apiPath.endsWith('/workflows/11/runs') && method === 'GET') return respond({ items: lastWorkflowRun ? [lastWorkflowRun] : [], total: lastWorkflowRun ? 1 : 0, page: 1, page_size: 10, total_pages: lastWorkflowRun ? 1 : 0 })
    if (apiPath.endsWith('/workflows/11/run') && method === 'POST') {
      workflowRuns += 1
      lastWorkflowRun = { id: 501, workflow_id: 11, status: 'completed', context_version: context.version, error: null, nodes: [{ request_id: 601, node_id: 21, node_key: 'requirements', node_type: 'requirements_analysis', status: 'completed', result: { result_type: 'requirements_analysis', summary: '虚构工作流结果', requirements: ['页面闭环'] }, error: null, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, latency_ms: 800, requested_at: now, finished_at: now }], started_at: now, finished_at: now, created_at: now }
      return respond(lastWorkflowRun, 201)
    }
    errors.push(`未预期的 API 请求 ${method} ${apiPath}`)
    return respond({ error: { code: 'unexpected', message: 'Unexpected fake request', request_id: 'fake' } }, 500)
  })

  try {
    await page.goto(`${baseUrl}/projects/7/ai`)
    await page.getByRole('heading', { name: `${project.name} · AI 工作台` }).waitFor()
    assert.equal(modelCalls, 0, '进入页面不能自动调用模型')
    await page.getByRole('button', { name: '创建项目 Context' }).click()
    await page.getByText('Context 已从当前项目资料创建。此操作没有调用模型。').waitFor()
    assert.equal(modelCalls, 0, '创建 Context 不能调用模型')

    await page.getByLabel('主要语言').fill('TypeScript')
    await page.getByRole('button', { name: /保存 Context v1/ }).click()
    await page.getByText('Context 版本已变化。你的草稿仍保留').waitFor()
    assert.equal(await page.getByLabel('主要语言').inputValue(), 'TypeScript', '冲突时应保留草稿')
    await page.getByRole('button', { name: '载入最新版本' }).click()
    assert.equal(await page.getByLabel('主要语言').inputValue(), 'Python')

    await page.getByLabel('主要语言').fill('TypeScript')
    await page.getByRole('button', { name: /保存 Context v1/ }).click()
    await page.getByText(/Context 已保存为 v2/).waitFor()
    await page.getByText('节点 #21').waitFor()

    await page.getByLabel('分析重点（可选）').fill('权限边界和版本冲突')
    await page.getByRole('button', { name: '运行需求分析' }).click()
    await page.getByRole('heading', { name: '需求分析结果' }).waitFor()
    assert.equal(modelCalls, 1)
    await page.getByRole('button', { name: '刷新结果' }).click()
    assert.equal(resultQueries, 1, '结果刷新应按请求编号查询')
    await page.screenshot({ path: path.join(evidenceDir, 'P20_AI工作台_需求分析_桌面.png'), fullPage: true })

    await page.getByRole('tab', { name: '开发 Prompt' }).click()
    await page.getByRole('button', { name: '生成开发 Prompt' }).click()
    await page.getByRole('heading', { name: '开发 Prompt 结果' }).waitFor()
    assert.equal(modelCalls, 2)
    await page.getByRole('button', { name: '复制开发 Prompt' }).click()
    assert.match(await page.evaluate(() => navigator.clipboard.readText()), /实现 Context 编辑/)

    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: path.join(evidenceDir, 'P20_AI工作台_Prompt_窄屏.png'), fullPage: true })
    const overflow = await page.locator('.ai-workspace-page').evaluate(element => element.scrollWidth - element.clientWidth)
    assert.ok(overflow <= 1, `窄屏内容不应横向溢出，实际 ${overflow}px`)

    context = makeContext(2, { is_stale: true, stale_fields: ['language'], stale_node_ids: [21, 22, 23] })
    await page.reload()
    await page.getByText('Context 与项目资料不一致', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: '运行需求分析' }).isDisabled(), true)
    const writesBeforeSync = contextWrites
    await page.getByRole('button', { name: '同步项目变更' }).click()
    await page.getByText(/已同步项目字段/).waitFor()
    assert.equal(contextWrites, writesBeforeSync + 1)
    assert.equal(modelCalls, 2, '同步 Context 不能调用模型')

    context = makeContext(3, { stale_node_ids: [21, 22, 23] })
    await page.setViewportSize({ width: 1440, height: 1050 })
    const writesBeforeWorkflow = contextWrites
    await page.goto(`${baseUrl}/workflows/11`)
    await page.getByText('受 Context 更新影响：需求分析、技术栈分析、架构设计').waitFor()
    assert.equal(contextWrites, writesBeforeWorkflow, '进入工作流不能静默同步 Context')
    await page.getByRole('button', { name: '运行 AI' }).click()
    await page.getByText('虚构工作流结果').waitFor()
    assert.equal(workflowRuns, 1)
    assert.equal(contextWrites, writesBeforeWorkflow, '运行工作流前不能静默改写 Context')
    await page.screenshot({ path: path.join(evidenceDir, 'P20_工作流运行结果_桌面.png'), fullPage: true })

    assert.deepEqual(errors, [])
    console.log('PASS: Context 创建、版本冲突、显式同步、两类 Agent、结果复制、三节点 Workflow、长文本、桌面与窄屏')
  } catch (error) {
    console.error({ url: page.url(), text: await page.locator('body').innerText(), errors })
    throw error
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
