// L4 浏览器：凭据只从父进程 stdin 取得；API 转发到专用隔离服务，不伪造业务响应。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const fixture = JSON.parse(fs.readFileSync(0, 'utf8'))
const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4181'
const backendUrl = 'http://127.0.0.1:8001'
const evidence = process.env.SCHOLARHUB_BROWSER_EVIDENCE_DIR || path.resolve(__dirname, '../../开发相关文档/测试证据/L4')
const errors = []
const checks = []
let apiRequests = 0

async function login(browser, account) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    apiRequests++
    // 已有构建指向默认开发端口；仅改传输地址，保留真实状态码、响应体和鉴权。
    const response = await route.fetch({ url: backendUrl + url.pathname + url.search })
    if (response.status() >= 500) errors.push(`${route.request().method()} ${url.pathname}: ${response.status()}`)
    await route.fulfill({ response })
  })
  await page.goto(baseUrl + '/login')
  await page.getByLabel('用户名或邮箱').fill(account.username)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  const slider = page.getByRole('slider', { name: '滑块验证' })
  await page.locator('.slider-captcha.is-ready').waitFor()
  await slider.click({ trial: true })
  const handle = await slider.boundingBox()
  const track = await page.locator('.slider-captcha__track').boundingBox()
  const start = handle.x + handle.width / 2
  const end = track.x + track.width - handle.width / 2 - 5
  const y = handle.y + handle.height / 2
  await page.mouse.move(start, y)
  await page.mouse.down()
  for (let step = 1; step <= 20; step++) {
    await page.mouse.move(start + (end - start) * step / 20, y)
    await page.waitForTimeout(30)
  }
  await page.mouse.up()
  await page.getByText('验证通过', { exact: true }).waitFor()
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.waitForLoadState('networkidle')
  return page
}

async function refreshed(page, route, ready) {
  await page.goto(baseUrl + route)
  await ready()
  await page.reload()
  await ready()
}

async function verifyHistory(page, label) {
  await refreshed(page, `/campus/submissions/${fixture.submission_id}`, async () => {
    await page.getByText('V2 · 已通过', { exact: true }).waitFor()
    await page.getByText('V1 · 已退回', { exact: true }).waitFor()
    assert.equal(await page.locator('.submission-version').count(), 2)
    assert.equal(await page.locator('.feedback-result').count(), 2)
    await page.getByText('L4 请补充空字符串和中文测试。', { exact: true }).waitFor()
    await page.getByText('L4 两类测试齐全，确认通过。', { exact: true }).waitFor()
  })
  await page.locator('.teaching-page').screenshot({ path: path.join(evidence, `${label}-版本反馈.png`) })
  checks.push(`${label}重新查询V1退回/V2通过及两条反馈`)
}

async function main() {
  fs.mkdirSync(evidence, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  try {
    const student = await login(browser, fixture.accounts[0])
    await refreshed(student, `/projects/${fixture.practice_project_id}`, async () => {
      await student.getByRole('heading', { name: 'L4 待实践项目 B', exact: true }).waitFor()
      await student.locator('.status-chip[data-status="in_progress"]').waitFor()
    })
    checks.push('项目刷新保持进行中，教师通过未自动完成个人项目')
    await refreshed(student, '/learning/tasks', async () => {
      const row = student.locator('.learning-task-board > li').filter({ hasText: 'L4 尚待本人完成的实践' })
      await row.waitFor()
      assert.equal(await row.getByRole('button', { name: '完成', exact: true }).count(), 1)
    })
    checks.push('个人任务刷新仍待完成')
    await refreshed(student, `/workflows/${fixture.workflow_id}`, async () => {
      await student.locator('.workflow-run-history > button').first().waitFor()
      assert.equal(await student.locator('.workflow-run-history > button').count(), 4)
      assert.match(await student.locator('.workflow-run-history').innerText(), /失败/)
      await student.locator('.workflow-node-result').first().waitFor()
      assert.equal(await student.locator('.workflow-node-result').count(), 3)
    })
    checks.push('Workflow刷新保留失败及恢复后的运行与节点结果')
    await verifyHistory(student, '学生')
    await refreshed(student, '/notifications', async () => {
      await student.locator('.notification-item').first().waitFor()
      assert.equal(await student.getByRole('heading', { name: '你的成果收到反馈', exact: true }).count(), 2)
    })
    checks.push('通知刷新保留两次教师反馈')
    await refreshed(student, '/analytics', async () => {
      const facts = student.locator('.analytics-report-facts .number-roller')
      await facts.first().waitFor()
      assert.deepEqual(await facts.evaluateAll(nodes => nodes.map(node => node.getAttribute('aria-label'))), [
        String(fixture.report_facts.total_learning_minutes), String(fixture.report_facts.active_days),
        `${fixture.report_facts.task_completion_rate}%`,
      ])
    })
    await student.locator('.analytics-report-detail').screenshot({ path: path.join(evidence, '报告真实刷新.png') })
    checks.push('报告刷新使用生成时事实，未被后续记录覆盖')

    await student.goto(baseUrl + `/projects/${fixture.project_id}/ai`)
    await student.getByLabel('按结果编号查询').fill(String(fixture.agent_request_id))
    await student.getByRole('button', { name: '刷新结果', exact: true }).click()
    await student.getByRole('heading', { name: '开发 Prompt 结果', exact: true }).waitFor()
    await student.goto(baseUrl + '/learning/tasks')
    await student.getByRole('button', { name: '创建任务', exact: true }).first().click()
    const taskEditor = student.locator('.learning-editor')
    await taskEditor.getByLabel('任务标题', { exact: true }).fill('L4 人工采纳 AI 建议后的验收任务')
    await taskEditor.locator('label').filter({ hasText: '关联计划' }).locator('select').selectOption(String(fixture.practice_plan_id))
    await taskEditor.locator('label').filter({ hasText: '关联项目' }).locator('select').selectOption(String(fixture.practice_project_id))
    await taskEditor.getByRole('button', { name: '创建任务', exact: true }).click()
    await taskEditor.waitFor({ state: 'hidden' })
    const manualTask = student.locator('.learning-task-board > li').filter({ hasText: 'L4 人工采纳 AI 建议后的验收任务' })
    const completion = student.waitForResponse(response => /\/learning\/tasks\/\d+\/complete$/.test(new URL(response.url()).pathname) && response.request().method() === 'POST')
    await manualTask.getByRole('button', { name: '完成', exact: true }).click()
    assert.equal((await completion).status(), 200)
    await student.reload()
    await manualTask.waitFor()
    assert.equal(await manualTask.getByRole('button', { name: '完成', exact: true }).count(), 0)
    await student.goto(baseUrl + '/learning/records')
    await student.getByRole('button', { name: '记录学习', exact: true }).click()
    const recordEditor = student.locator('.learning-editor')
    await recordEditor.getByLabel('记录标题', { exact: true }).fill('L4 人工记录虚构实践过程')
    await recordEditor.getByLabel('学习时长（分钟）', { exact: true }).fill('12')
    await recordEditor.locator('label').filter({ hasText: '关联项目' }).locator('select').selectOption(String(fixture.practice_project_id))
    await recordEditor.getByRole('button', { name: '保存记录', exact: true }).click()
    await recordEditor.waitFor({ state: 'hidden' })
    await student.reload()
    await student.getByRole('heading', { name: 'L4 人工记录虚构实践过程', exact: true }).waitFor()
    checks.push('AI结果经人工选择→新建任务→本人完成→主动保存记录并刷新')

    const teacher = await login(browser, fixture.accounts[3])
    await refreshed(teacher, `/campus/classes/${fixture.class_id}`, async () => {
      await teacher.getByRole('heading', { name: 'L4 虚构教学班 A', exact: true }).waitFor()
    })
    await verifyHistory(teacher, '教师')

    const viewer = await login(browser, fixture.accounts[1])
    await refreshed(viewer, `/community/projects/${fixture.project_id}`, async () => {
      await viewer.getByRole('heading', { level: 1 }).waitFor()
      assert.equal(await viewer.getByText('L4 审核后私人变更', { exact: true }).count(), 0)
    })
    await viewer.goto(baseUrl + '/projects')
    await viewer.getByRole('button', { name: '创建项目', exact: true }).first().click()
    const projectForm = viewer.locator('.project-form')
    await projectForm.getByLabel('项目名称', { exact: true }).fill('L4 参考社区后独立创建的项目')
    await projectForm.getByLabel('项目说明', { exact: true }).fill(`人工参考社区作品 #${fixture.project_id}；这是重新录入的独立虚构实践项目。`)
    await projectForm.getByRole('button', { name: '创建项目', exact: true }).click()
    await viewer.waitForURL(url => /^\/projects\/\d+$/.test(url.pathname))
    const manualProjectId = Number(new URL(viewer.url()).pathname.split('/').at(-1))
    assert.notEqual(manualProjectId, fixture.project_id)
    await viewer.reload()
    await viewer.getByRole('heading', { name: 'L4 参考社区后独立创建的项目', exact: true }).waitFor()
    await viewer.locator('.project-detail-page').screenshot({ path: path.join(evidence, '社区参考后人工创建.png') })
    checks.push('公开快照刷新→人工记录来源→独立创建个人项目并刷新')
    assert.deepEqual(errors, [])
    console.log(JSON.stringify({ browser_mainline: 'passed', apiRequests, checks, manualProjectId, pageErrors: errors.length }))
  } finally {
    await browser.close()
  }
}

main().catch(error => {
  console.error(`L4 browser failed: ${error.message}`)
  process.exitCode = 1
})
