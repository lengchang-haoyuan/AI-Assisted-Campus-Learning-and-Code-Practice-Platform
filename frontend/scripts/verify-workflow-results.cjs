// 工作流结果浏览器回归：所有 API 使用虚构 Mock，独立浏览器会话，不访问数据库或真实模型。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:5173'
const frontendOrigin = new URL(baseUrl).origin
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseUrl).hostname), '只允许本地前端验收')
const evidenceDir = process.env.SCHOLARHUB_WORKFLOW_EVIDENCE || path.resolve(__dirname, '../../开发相关文档/测试证据/20261018-工作流结果')
const now = '2026-10-18T07:00:00Z'
const projectId = 7
const workflowId = 23
const pageData = items => ({ items, total: items.length, page: 1, page_size: 10, total_pages: items.length ? 1 : 0 })
const untrustedHtml = '<img src="invalid-workflow-fixture" onerror="window.__workflowInjected=true">'

function requirements(summary, prefix) {
  return {
    result_type: 'requirements_analysis', summary,
    requirements: [
      { title: `${prefix}·项目列表`, description: '按关键词查看项目，并在独立详情中阅读项目内容。', acceptance_criteria: ['关键词筛选正确', '空列表提示清楚', '详情入口可用'], legacy_priority: '[MOCK] 历史需求扩展字段' },
      { title: `${prefix}·结果查看`, description: '选择运行记录中的单个节点，阅读当前节点的结构化分析。', acceptance_criteria: ['切换节点不会混入其他结果'] },
      { title: `${prefix}·运行历史`, description: '刷新历史记录后保持当前节点。', acceptance_criteria: ['运行记录仍可选择', '相同类型节点可区分'] },
    ],
    features: ['项目筛选', '节点结果导航', '运行历史查询'],
    constraints: ['[MOCK] 仅用于浏览器回归的虚构内容', '仅展示分析，不执行用户代码'],
    historical_extra: { note: untrustedHtml, count: 0, enabled: false },
  }
}

function architecture(summary, prefix) {
  return {
    result_type: 'architecture_design', summary, style: '分层架构',
    components: [
      { name: `${prefix}浏览器`, responsibility: '展示运行历史和节点结果。', technology: 'Vue 3', dependencies: [`${prefix}接口`] },
      { name: `${prefix}接口`, responsibility: '校验权限后读取已保存结果。', technology: 'FastAPI', dependencies: [`${prefix}数据存储`] },
      { name: `${prefix}数据存储`, responsibility: '保存节点结果及运行状态。', technology: 'MySQL', dependencies: [] },
    ],
    data_flows: [
      { source: `${prefix}浏览器`, target: `${prefix}接口`, data: '运行记录查询参数' },
      { source: `${prefix}接口`, target: `${prefix}数据存储`, data: '按运行编号读取节点结果' },
      { source: `${prefix}数据存储`, target: `${prefix}浏览器`, data: '已保存的结构化节点结果' },
    ],
    decisions: [{ title: '结果持久化', choice: '读取历史结果', reason: '选择或刷新节点时无需再次调用模型。' }],
  }
}

function node(requestId, key, type, result, overrides = {}) {
  return {
    request_id: requestId, node_id: requestId % 100, node_key: key, node_type: type,
    status: 'completed', result, error: null,
    prompt_tokens: 120, completion_tokens: 280, total_tokens: 400, latency_ms: 1250,
    requested_at: now, finished_at: now, ...overrides,
  }
}

function run(id, nodes, overrides = {}) {
  return {
    id, workflow_id: workflowId, status: 'completed', context_version: 3, error: null,
    nodes, started_at: now, finished_at: now, created_at: now, ...overrides,
  }
}

const markers = {
  requirementsA: '[MOCK] 运行35的需求分析A，验收项数量为3、1、2。',
  architecture: '[MOCK] 运行35的架构设计，只在选择架构节点时显示。',
  requirementsB: '[MOCK] 运行35的需求分析B，与同类型A使用不同请求编号。',
  stack: '[MOCK] 零用量技术栈节点，零值应保留。',
  previousRequirements: '[MOCK] 运行34的旧需求，不应混入运行35。',
  previousArchitecture: '[MOCK] 运行34的旧架构，耗时与用量尚未统计。',
}
const initialRuns = [
  run(35, [
    node(3501, 'requirements-primary', 'requirements_analysis', requirements(markers.requirementsA, '需求A')),
    node(3502, 'architecture-main', 'architecture_design', architecture(markers.architecture, '当前')),
    node(3503, 'requirements-secondary', 'requirements_analysis', requirements(markers.requirementsB, '需求B')),
    node(3504, 'stack-zero', 'tech_stack_analysis', {
      result_type: 'tech_stack_analysis', summary: markers.stack,
      language: { value: 'TypeScript', reason: '复用现有类型系统。' },
      framework: { value: 'Vue 3', reason: '复用现有框架。' },
      frontend: { value: 'Vue 3', reason: '保留当前交互。' },
      backend: { value: 'FastAPI', reason: '使用现有接口。' },
      database: { value: 'MySQL', reason: '读取已保存结果。' },
    }, { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, latency_ms: 0 }),
  ]),
  run(34, [
    node(3401, 'requirements-old', 'requirements_analysis', requirements(markers.previousRequirements, '旧需求')),
    node(3402, 'architecture-old', 'architecture_design', architecture(markers.previousArchitecture, '历史'), {
      prompt_tokens: null, completion_tokens: null, total_tokens: null, latency_ms: null,
    }),
  ], { created_at: '2026-10-17T07:00:00Z' }),
  run(33, [node(3301, 'requirements-failed', 'requirements_analysis', null, {
    status: 'failed', error: { code: 'agent_output_invalid', message: '[MOCK] 节点结果校验未通过' },
    prompt_tokens: null, completion_tokens: null, total_tokens: null, latency_ms: null,
  })], { status: 'failed', error: { code: 'agent_output_invalid', message: '[MOCK] 本次运行失败' }, created_at: '2026-10-16T07:00:00Z' }),
  run(32, [], { created_at: '2026-10-15T07:00:00Z' }),
]
const fieldNames = ['project_name', 'language', 'framework', 'frontend', 'backend', 'database', 'difficulty', 'requirements', 'output_requirement', 'architecture', 'features', 'constraints', 'extensions']
const source = { type: 'project', id: projectId, node_key: null }
const projectContext = {
  project_id: projectId, version: 3,
  values: { project_name: '[MOCK] 节点结果验收', language: 'TypeScript', framework: 'Vue 3', frontend: 'Vue 3', backend: 'FastAPI', database: 'MySQL', difficulty: 'beginner', requirements: [], output_requirement: '查看已保存结果', architecture: {}, features: [], constraints: [], extensions: {} },
  field_metadata: Object.fromEntries(fieldNames.map(field => [field, { version: 3, updated_at: now, source }])),
  updated_at: now, source, is_stale: false, stale_fields: [], stale_node_ids: [],
}
const graphNodes = initialRuns[0].nodes.map((item, index) => ({
  id: item.node_id, workflow_id: workflowId, node_key: item.node_key, node_type: item.node_type,
  name: ['需求分析A', '架构设计', '需求分析B', '技术栈分析'][index],
  position_x: 80 + index * 280, position_y: 120, config: { instruction: '仅用于Mock页面验收', expected_output: '' },
  status: 'success', context_version: 3, created_at: now, updated_at: now,
}))
const graph = {
  workflow: { id: workflowId, project: { id: projectId, name: '[MOCK] 节点结果验收' }, name: '[MOCK] 节点模块化结果回归', description: '浏览器中的虚构记录', status: 'completed', version: 4, node_count: graphNodes.length, edge_count: 3, created_at: now, updated_at: now },
  nodes: graphNodes,
  edges: graphNodes.slice(1).map((item, index) => ({ id: 80 + index, workflow_id: workflowId, source_node_id: graphNodes[index].id, target_node_id: item.id, source_node_key: graphNodes[index].node_key, target_node_key: item.node_key, condition_data: null, created_at: now })),
}

async function main() {
  fs.mkdirSync(evidenceDir, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, timezoneId: 'Asia/Shanghai' })
  await context.addInitScript(() => {
    sessionStorage.setItem('scholarhub.access_token', 'workflow-results-isolated-mock-token')
    // 复制操作只写入此隔离页面的变量，避免覆盖用户系统剪贴板。
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async value => { window.__workflowClipboard = value } } })
  })
  const page = await context.newPage()
  const errors = []
  const requests = []
  const blockedWrites = []
  const blockedExternalRequests = []
  const checks = []
  let runs = structuredClone(initialRuns)
  page.on('pageerror', error => errors.push(error.message))
  // 拦截全部API及外部请求，即便出现未预期端点也不会落到业务服务。
  await context.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()
    if (!url.pathname.startsWith('/api/')) {
      if (url.origin === frontendOrigin || ['data:', 'blob:'].includes(url.protocol)) return route.continue()
      blockedExternalRequests.push({ method, origin: url.origin, pathname: url.pathname })
      return route.abort('blockedbyclient')
    }
    const endpoint = url.pathname.replace('/api/v1', '')
    requests.push({ method, endpoint, query: url.search })
    const respond = (json, status = 200) => route.fulfill({ status, json })
    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': frontendOrigin, 'access-control-allow-headers': 'authorization,content-type', 'access-control-allow-methods': 'GET' } })
    if (method !== 'GET') {
      blockedWrites.push({ method, endpoint })
      return respond({ error: { code: 'isolated_test_write_blocked', message: 'Mock回归不允许写请求' } }, 405)
    }
    if (endpoint === '/users/me') return respond({ id: 1, username: 'workflow_mock_student', email: 'workflow@example.test', avatar_url: null, bio: null, is_active: true, created_at: now, updated_at: now })
    if (endpoint === '/campus/me') return respond({ campus: null, membership: null })
    if (endpoint === `/workflows/${workflowId}/graph`) return respond(graph)
    if (endpoint === `/projects/${projectId}/context`) return respond(projectContext)
    if (endpoint === `/workflows/${workflowId}/runs`) return respond(pageData(runs))
    errors.push(`未预期的Mock API请求 ${method} ${endpoint}`)
    return respond({ error: { code: 'unexpected_mock_endpoint', message: '未知Mock端点' } }, 500)
  })
  const panel = page.locator('.workflow-execution')
  const result = panel.locator('.workflow-node-result')
  const runButton = id => panel.locator('.workflow-run-entry__trigger').filter({ hasText: new RegExp(`运行 #${id}\\b`) })
  const nodeButton = (name, index = 0) => panel.locator('.workflow-run-node-list').getByRole('button', { name: new RegExp(name) }).nth(index)
  const shownSummary = async marker => {
    await result.getByText(marker, { exact: true }).waitFor()
    assert.equal(await result.count(), 1, '右侧每次仅展示所选的一个节点')
    const content = await result.innerText()
    for (const other of Object.values(markers)) if (other !== marker) assert.ok(!content.includes(other), `不应混入其他节点：${other}`)
  }
  const selectRun = async id => {
    await runButton(id).click()
    await panel.locator('.workflow-run-results').getByRole('heading', { name: new RegExp(`运行 #${id}\\b`) }).waitFor()
  }
  const refresh = async () => {
    const response = page.waitForResponse(item => new URL(item.url()).pathname === `/api/v1/workflows/${workflowId}/runs`)
    await panel.getByRole('button', { name: '刷新运行记录', exact: true }).click()
    await response
    await panel.getByRole('button', { name: '刷新运行记录', exact: true }).waitFor()
  }
  const noOverflow = async width => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1050 })
    await page.evaluate(() => document.fonts.ready)
    const size = await panel.evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth }))
    assert.ok(size.scroll <= size.client + 1, `结果面板在${width}px有横向溢出：${size.scroll}/${size.client}`)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `页面在${width}px有横向溢出`)
  }
  // 截取结果面板时隐藏固定导航与复制提示，避免它们遮挡长面板截图中的分析内容。
  const screenshot = filename => panel.screenshot({
    path: path.join(evidenceDir, filename),
    style: '.app-topbar, .studio-mobile-navigation, .el-message { visibility: hidden !important; }',
  })

  try {
    await page.goto(`${baseUrl}/workflows/${workflowId}`)
    await panel.getByRole('heading', { name: 'AI 运行与结果', exact: true }).waitFor()
    await shownSummary(markers.requirementsA)
    assert.equal(await panel.locator('.workflow-run-history').getByRole('button', { name: /需求分析/ }).count(), 2, '当前运行应展开两个同类型需求节点')
    checks.push('选择运行记录后展开该记录的节点列表，默认仅显示一个节点')

    await nodeButton('架构设计').click()
    await shownSummary(markers.architecture)
    const flowRows = result.locator('.workflow-data-flows > li')
    assert.equal(await flowRows.count(), 3)
    assert.deepEqual(await flowRows.nth(0).locator('.workflow-data-flows__route strong').allTextContents(), ['当前浏览器', '当前接口'])
    assert.match(await flowRows.nth(0).innerText(), /运行记录查询参数/)
    assert.equal(await result.locator('.workflow-architecture-modules > article').count(), 3)
    checks.push('选择节点后仅显示对应节点结果')
    checks.push('架构数据流按真实source/target/data生成，展示模块职责')
    await screenshot('mock-desktop-architecture.png')

    await result.getByRole('button', { name: '下一个节点', exact: true }).focus()
    await page.keyboard.press('Enter')
    await shownSummary(markers.requirementsB)
    await page.waitForFunction(() => document.activeElement?.id === 'workflow-selected-node-title')
    checks.push('键盘激活下一个节点后焦点移动到新节点标题')
    await result.getByRole('button', { name: '上一个节点', exact: true }).click()
    await shownSummary(markers.architecture)
    await result.getByRole('button', { name: '上一个节点', exact: true }).click()
    await shownSummary(markers.requirementsA)
    assert.equal(await result.getByRole('button', { name: '上一个节点', exact: true }).isDisabled(), true)
    checks.push('上一个/下一个节点沿当前运行顺序切换，首节点禁用向前按钮')

    await nodeButton('需求分析', 1).focus()
    await page.keyboard.press('Enter')
    await shownSummary(markers.requirementsB)
    checks.push('同类型节点按request_id区分，键盘可切换')
    await result.getByRole('button', { name: '复制结果', exact: true }).click()
    assert.deepEqual(JSON.parse(await page.evaluate(() => window.__workflowClipboard)), initialRuns[0].nodes[2].result)
    checks.push('复制仅输出当前节点完整JSON，使用Mock剪贴板')
    await selectRun(34)
    await shownSummary(markers.previousRequirements)
    await nodeButton('架构设计').click()
    await shownSummary(markers.previousArchitecture)
    await selectRun(35)
    await shownSummary(markers.requirementsB)
    await selectRun(34)
    await shownSummary(markers.previousArchitecture)
    checks.push('跨运行切换分别恢复各运行所选节点')

    await selectRun(35)
    await refresh()
    await shownSummary(markers.requirementsB)
    checks.push('刷新同一运行记录保持所选request_id')

    await nodeButton('技术栈分析').click()
    await shownSummary(markers.stack)
    assert.equal(await result.getByRole('button', { name: '下一个节点', exact: true }).isDisabled(), true)
    assert.match(await result.innerText(), /0\s*tokens/i, '0 tokens不能显示为待统计')
    assert.match(await result.innerText(), /0(?:\.0)?\s*(?:秒|s)/, '0毫秒不能显示为待统计')
    await panel.locator('.workflow-run-chart > summary').click()
    assert.match(await panel.locator('.workflow-run-chart__rows > li').last().innerText(), /0\.0\s*秒/)
    await panel.getByLabel('统计指标').selectOption('total_tokens')
    assert.match(await panel.locator('.workflow-run-chart__rows > li').last().innerText(), /0\s*tokens/)
    await selectRun(34)
    await shownSummary(markers.previousArchitecture)
    assert.match(await result.innerText(), /耗时\s*待统计/)
    assert.match(await result.innerText(), /用量\s*待统计/)
    assert.match(await panel.locator('.workflow-run-chart__rows > li').last().innerText(), /待统计/)
    checks.push('零值保留，null耗时及用量显示待统计')

    await selectRun(33)
    await result.getByText('[MOCK] 节点结果校验未通过', { exact: false }).waitFor()
    assert.equal(await result.getByRole('button', { name: '复制结果', exact: true }).count(), 0)
    assert.equal(await result.locator('canvas, svg').count(), 0, '失败无结果不应出现旧节点图表')
    await screenshot('mock-failed-node.png')
    checks.push('失败且无result时显示节点错误，不遗留旧图表或复制按钮')

    await selectRun(32)
    await panel.getByText('本次运行尚未生成节点记录，刷新后可查看最新状态。', { exact: true }).waitFor()
    assert.equal(await result.count(), 0)
    checks.push('空节点运行显示空态')

    await selectRun(35)
    await nodeButton('需求分析', 0).click()
    await shownSummary(markers.requirementsA)
    const criteriaRows = result.locator('.workflow-acceptance-chart li')
    assert.equal(await criteriaRows.count(), 3)
    assert.deepEqual(await criteriaRows.locator('strong').allTextContents(), ['3 项', '1 项', '2 项'])
    assert.equal(await result.locator('.workflow-requirement-list > li').count(), 3)
    checks.push('需求验收项图表按实际3/1/2项生成，保留全部需求与验收文本')
    await result.getByText('[MOCK] 历史需求扩展字段', { exact: true }).waitFor()
    const extension = result.locator('[data-field="historical_extra"]')
    assert.match(await extension.innerText(), /count：0/)
    assert.match(await extension.innerText(), /enabled：false/)
    assert.ok((await extension.innerText()).includes(untrustedHtml))
    assert.equal(await result.locator('img').count(), 0)
    assert.equal(await page.evaluate(() => window.__workflowInjected), undefined)
    checks.push('未知与历史扩展字段完整保留，HTML作为文本展示且不执行')
    await noOverflow(1440)
    await screenshot('mock-desktop-requirements.png')
    await noOverflow(390)
    const history = panel.locator('.workflow-run-history')
    const selectedEntrySize = await history.locator('.workflow-run-entry.is-selected').evaluate(element => ({ client: element.clientHeight, scroll: element.scrollHeight }))
    assert.ok(selectedEntrySize.scroll <= selectedEntrySize.client + 1, `390px展开运行卡片内容被压缩裁切：${selectedEntrySize.scroll}/${selectedEntrySize.client}`)
    const mobileNodeMarkers = [markers.requirementsA, markers.architecture, markers.requirementsB, markers.stack]
    for (let index = 0; index < mobileNodeMarkers.length; index += 1) {
      const control = history.locator('.workflow-run-node-list button').nth(index)
      await control.scrollIntoViewIfNeeded()
      const visibility = await control.evaluate(button => {
        const scrollArea = button.closest('.workflow-run-history').getBoundingClientRect()
        const bounds = button.getBoundingClientRect()
        return { top: bounds.top - scrollArea.top, bottom: scrollArea.bottom - bounds.bottom }
      })
      assert.ok(visibility.top >= -1 && visibility.bottom >= -1, `390px第${index + 1}个节点无法完整滚入历史区域`)
      await control.click()
      await shownSummary(mobileNodeMarkers[index])
      assert.equal(await control.getAttribute('aria-pressed'), 'true')
    }
    await nodeButton('需求分析', 0).scrollIntoViewIfNeeded()
    await nodeButton('需求分析', 0).click()
    await shownSummary(markers.requirementsA)
    await history.evaluate(element => { element.scrollTop = 0 })
    checks.push('390px展开卡片不压缩裁切，历史滚动区中全部节点可滚入并点选')
    await screenshot('mock-mobile-requirements.png')
    await nodeButton('架构设计').click()
    await shownSummary(markers.architecture)
    await history.evaluate(element => { element.scrollTop = 0 })
    await noOverflow(390)
    await screenshot('mock-mobile-architecture.png')
    checks.push('桌面与390px窄屏无横向溢出')

    runs = []
    await refresh()
    await panel.getByText(/还没有运行记录/).waitFor()
    assert.equal(await result.count(), 0)
    await screenshot('mock-empty-history.png')
    checks.push('无运行记录显示空态')

    assert.deepEqual(errors, [], '不应出现浏览器运行错误或未知API')
    assert.deepEqual(blockedWrites, [], '查看及刷新结果不能触发写API或模型API')
    const verification = {
      result: 'passed', evidence_type: 'Mock browser regression', checks,
      API_requests_intercepted: requests.length, database_writes: 0, model_calls: 0,
      blocked_writes: blockedWrites, blocked_external_requests: blockedExternalRequests,
      viewport_widths: [1440, 390], fixture_run_ids: initialRuns.map(item => item.id),
    }
    fs.writeFileSync(path.join(evidenceDir, 'mock-verification.json'), JSON.stringify(verification, null, 2))
    console.log(JSON.stringify(verification))
  } catch (error) {
    await page.screenshot({ path: path.join(evidenceDir, 'mock-failure.png'), fullPage: true }).catch(() => {})
    console.error(JSON.stringify({ result: 'failed', evidence_type: 'Mock browser regression', url: page.url(), checks, errors, blockedWrites, message: error.message }))
    throw error
  } finally { await browser.close() }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
