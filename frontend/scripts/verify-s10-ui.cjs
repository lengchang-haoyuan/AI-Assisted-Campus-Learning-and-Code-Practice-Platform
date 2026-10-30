// S10新版/旧版混合批次与一次建议应用；所有API为显式Mock，无数据库或模型调用。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')
const root = path.resolve(__dirname, '../..')
const output = path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2/S10-证据/frontend-mock')
const url = process.env.S10_UI_URL || 'http://127.0.0.1:4198'
const clone = value => structuredClone(value)
const uid = number => `a0000000-0000-4000-8000-${String(number).padStart(12, '0')}`
const oldId = uid(1), newId = uid(2), now = '2026-10-26T08:00:00Z'
const payload = JSON.parse(fs.readFileSync(path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2/S05-发布输入/v2-controlled/payload.json'), 'utf8'))
const { owner_user_id, source_counts, dataset_id, snapshot_id, job_id, ...oldFields } = payload
const old = { ...oldFields, batch_id: oldId, published_at: now, source: { dataset_id, snapshot_id, job_id } }
const advice = number => ({ attempt_id: uid(20 + number), attempt_no: number, operation_id: uid(30 + number), ai_request_id: 100 + number,
  review_event_id: uid(40 + number), issue_event_id: uid(50 + number), criterion_id: 'C03', issue_type: 'zero_as_missing', prompt_version: 'practice-advisory-r1', source: 'ai_report' })
const session = (number, attempts, status) => ({ session_id: uid(10 + number), project_id: 701, template_id: 'python-learning-csv', template_version: '1.0',
  context_version: 1, revision: 9, current_step_key: 'implement', status, created_at: now, attempt_count: attempts,
  event_counts: { attempt_submitted: attempts }, latest_attempt_id: attempts ? uid(20 + attempts) : null, latest_attempt_no: attempts || null,
  latest_operation_id: null, latest_ai_request_id: null, personal_reviewed: status === 'completed', self_statement: null,
  output_comparison: 'unknown', teacher_confirmation: null, advice: number === 2 ? [advice(1), advice(2)] : [] })
const candidate = { candidate_key: 'B-R1-advisory-1.0:mock-session:C03:zero_as_missing:1.0', rule_version: 'B-R1-advisory-1.0', source: 'ai_report',
  session_id: uid(12), project_id: 701, template_id: 'python-learning-csv', template_version: '1.0', context_version: 1,
  session_revision: 9, attempt_id: uid(22), attempt_no: 2, criterion_id: 'C03', issue_type: 'zero_as_missing', references: [advice(1), advice(2)],
  title: '补一个零分钟边界自测（Mock）', explanation: 'Mock：AI在两份提交中重复报告了同类建议，可选择补一个零分钟自测。' }
const fresh = { ...clone(old), batch_id: newId, schema_version: 'scholarhub-source-2.0', metric_version: 'learning-process-2.0', rule_version: 'quality-2.0',
  topic_summary: { teaching: clone(old.topic_summary), practice: { semantics: 'advisory_process',
    cohort_rule: 'sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff', observed_event_coverage_start: now, coverage_basis: 'first_retained_owner_event',
    session_count: 4, attempt_count: 4, submission_event_count: 2, no_submission_count: 1, personal_end_count: 1, request_count: 2, cancel_count: 1, resume_count: 1,
    teacher_confirmation_count: null, sessions: [session(1, 1, 'completed'), session(2, 2, 'waiting_confirmation'), session(3, 0, 'waiting_submission'), session(4, 1, 'waiting_submission')] } },
  recommendations: [candidate] }
function emptyTeaching(value) {
  if (Array.isArray(value)) return value.map(emptyTeaching)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
    key === 'percent' || key === 'first_review_wait_mean_minutes' ? null : key === 'display' ? '无样本' : emptyTeaching(item)]))
  return typeof value === 'number' ? 0 : value
}
const practiceOnly = { ...clone(fresh), daily: [], records_summary: emptyTeaching(fresh.records_summary), tasks_summary: emptyTeaching(fresh.tasks_summary),
  topic_summary: { teaching: emptyTeaching(fresh.topic_summary.teaching), practice: clone(fresh.topic_summary.practice) } }
const project = { id: 701, name: 'S10 Mock CSV实践项目', description: '浏览器Mock，只验证界面', difficulty: 'beginner', status: 'not_started', tags: [], language: 'Python', framework: null, frontend: null, backend: null, database: null, requirements: [], output_requirement: null, progress: 0, created_at: now, updated_at: now }
const task = { id: 901, title: candidate.title, description: `建议来源\n/offline-analytics?batch_id=${newId}\n/projects/701/practice?session=${uid(12)}`, priority: 'medium', status: 'pending',
  scheduled_date: '2026-10-27', start_time: null, end_time: null, estimated_minutes: null, completed_at: null, plan: null, project: { id: 701, name: project.name }, created_at: now, updated_at: now }
const ordinaryTask = { ...clone(task), id: 902, title: '普通定位任务（Mock）', description: '没有建议应用映射的普通任务，仅用Mock验证成功删除。' }
const pageOf = items => ({ items, total: items.length, page: 1, page_size: 20, total_pages: items.length ? 1 : 0, empty_reason: null })
const checks = [], calls = [], errors = [], applications = []
let unsupported = false, malformedPractice = false, practiceOnlyMode = false, failApplication = true, activePage, ordinaryDeleted = false, heldTaskEdit = null
const result = { mode: 'mock', real_model_calls: 0, database_writes: 0, checks, errors, api_calls: calls, screenshots: [] }
const save = () => fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(result, null, 2))
async function check(name, run) { await run(); checks.push({ name, passed: true }); save() }

async function main() {
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' })
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' })
    await context.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 's10-mock-token'))
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(10000)
    page.on('pageerror', cause => errors.push(cause.message))
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), pathname = new URL(request.url()).pathname.replace('/api/v1', '')
      calls.push({ method: request.method(), path: pathname })
      const send = (data, status = 200) => route.fulfill({ status, json: clone(data) })
      if (pathname === '/users/me') return send({ id: 3, username: 's10_mock', email: 's10@example.invalid', is_active: true, created_at: now })
      if (pathname === '/campus/me') return send({ membership: null })
      if (pathname === '/offline-analytics/batches') return send(pageOf(unsupported ? [{ ...fresh, metric_version: 'learning-process-99.0' }, old] : [fresh, old]))
      if (pathname === `/offline-analytics/batches/${newId}`) return send(malformedPractice
        ? { ...fresh, topic_summary: { ...fresh.topic_summary, practice: { ...fresh.topic_summary.practice, session_count: Number.MAX_SAFE_INTEGER + 1 } } } : practiceOnlyMode ? practiceOnly : fresh)
      if (pathname === `/offline-analytics/batches/${oldId}`) return send(old)
      if (pathname.endsWith('/recommendation-applications')) {
        assert.equal(request.method(), 'POST')
        const body = request.postDataJSON(); applications.push(body)
        if (failApplication) { failApplication = false; return send({ error: { code: 'MOCK_BUSY', message: 'Mock：首次响应失败，可重试原请求', request_id: 'mock' } }, 503) }
        task.title = body.title; task.scheduled_date = body.scheduled_date
        return send({ application_id: uid(90), task_id: task.id, batch_id: newId, candidate_key: candidate.candidate_key, replayed: true, source_url: `/offline-analytics?batch_id=${newId}` })
      }
      if (pathname === '/projects') return send(pageOf([project]))
      if (pathname === '/projects/701') return send(project)
      if (pathname.startsWith('/learning/tasks') && request.headers().authorization === 'Bearer s10-mock-other') {
        return pathname === '/learning/tasks' ? send(pageOf([])) : send({ error: { code: 'NOT_FOUND', message: 'Mock：该任务不属于当前账号', request_id: 'mock' } }, 404)
      }
      if (pathname === '/learning/tasks/901/complete') {
        task.status = 'completed'; task.completed_at = now; return send(task)
      }
      if (pathname === '/learning/tasks/901') {
        if (request.method() === 'PUT') {
          const body = request.postDataJSON()
          Object.assign(task, body); task.title = `${body.title}（服务端结果）`
          if (heldTaskEdit) { const gate = heldTaskEdit; heldTaskEdit = null; gate.entered(); await gate.promise }
        }
        if (request.method() === 'DELETE') return send({ error: { code: 'CONFLICT', message: 'Mock：映射任务不可删除', request_id: 'mock' } }, 409)
        return send(task)
      }
      if (pathname === '/learning/tasks/902') {
        if (request.method() === 'DELETE') { ordinaryDeleted = true; return route.fulfill({ status: 204, body: '' }) }
        return ordinaryDeleted ? send({ error: { code: 'NOT_FOUND', message: 'Mock：普通任务已删除', request_id: 'mock' } }, 404) : send(ordinaryTask)
      }
      if (pathname === '/learning/tasks') return send(pageOf([task, ...(ordinaryDeleted ? [] : [ordinaryTask])]))
      if (pathname === '/learning/plans') return send(pageOf([]))
      return send({})
    })
    await page.goto(`${url}/offline-analytics?dataset_kind=controlled&batch_id=${newId}`)
    await check('新版与旧版混合列表可读，四张原教学图仍绑定完整新批次', async () => {
      await page.locator(`[data-practice-batch="${newId}"]`).waitFor()
      await page.locator('.offline-figure canvas').first().waitFor()
      assert.equal(await page.locator('.offline-figure canvas').count(), 4)
      assert.equal(await page.getByLabel('分析批次', { exact: true }).locator('option').count(), 2)
    })
    await check('实践动作与自我声明、输出核对、建议、本人和教师来源分列', async () => {
      await page.getByText('逐会话核对提交与来源（4）', { exact: true }).click()
      assert.equal(await page.locator('[data-session-id]').count(), 4)
      assert.ok((await page.locator(`[data-session-id="${uid(11)}"]`).innerText()).includes('已审阅本次材料'))
      assert.ok((await page.locator(`[data-session-id="${uid(13)}"]`).innerText()).includes('截至快照共0份提交'))
      assert.ok((await page.locator('[data-practice-batch]').innerText()).includes('未知 / 未提供'))
      assert.equal(calls.filter(call => call.method !== 'GET').length, 0)
    })
    await check('本周期提交动作与群组截至快照累计提交分开读取', async () => {
      const submission = page.locator('.offline-practice-measures > div').filter({ has: page.locator('dt', { hasText: '实际提交' }) })
      assert.equal(await submission.locator('dd').innerText(), '2')
      assert.equal(fresh.topic_summary.practice.attempt_count, 4)
      assert.ok((await page.locator(`[data-session-id="${uid(12)}"]`).innerText()).includes('截至快照共2份提交'))
      assert.ok((await page.locator('.offline-heading').innerText()).includes('本周期2次实际提交'))
    })
    await check('实践动作图绑定已发布窗口计数，tooltip为文本且保留无障碍数值', async () => {
      await page.locator('[data-practice-action-chart] canvas').waitFor()
      const chart = await page.locator('[data-practice-action-chart] .analytics-chart-wrap').evaluate(element => {
        const option = element.__vueParentComponent.props.option
        return { values: option.series[0].data, labels: option.yAxis.data, tooltip: option.tooltip.renderMode }
      })
      assert.deepEqual(chart.values, [2, 2, 1, 1, 1])
      assert.deepEqual(chart.labels, ['实际提交', 'AI 请求', '本人审阅结束', '取消', '恢复'])
      assert.equal(chart.tooltip, 'richText')
      assert.equal(await page.locator('.offline-practice-measures dt').count(), 7)
    })
    await check('仅实践样本时新图可绘制，四类旧数据分别保持合法空态', async () => {
      practiceOnlyMode = true
      await page.reload()
      await page.locator('.offline-figure .analytics-chart-empty').first().waitFor()
      assert.equal(await page.locator('.offline-figure').count(), 4)
      assert.equal(await page.locator('.offline-figure canvas').count(), 0)
      assert.equal(await page.locator('[data-practice-action-chart] canvas').count(), 1)
      assert.equal(await page.getByText('本批没有可绘制样本', { exact: true }).count(), 0)
      practiceOnlyMode = false
      await page.reload()
      await page.locator('.offline-figure canvas').first().waitFor()
    })
    await check('建议可展开确切attempt、operation、事件与规则引用', async () => {
      await page.getByText('核对建议原始引用与批次', { exact: true }).click()
      assert.equal(await page.locator('.offline-advice-references li').count(), 2)
      assert.ok((await page.locator('.offline-advice-references').innerText()).includes(uid(31)))
      assert.ok((await page.locator('[data-candidate]').innerText()).includes('不认定代码存在错误'))
    })
    await check('旧详情保持原图与五条规则，实践面板不会串到旧批次', async () => {
      await page.getByLabel('分析批次', { exact: true }).selectOption(oldId)
      await page.locator(`[data-batch-id="${oldId}"]`).waitFor()
      assert.equal(await page.locator('[data-practice-batch]').count(), 0)
      assert.equal(await page.locator('.offline-figure canvas').count(), 4)
      assert.equal(await page.locator('[data-rule]').count(), 5)
    })
    await check('新版实践字段强校验，异常计数不会借用旧DTO展示', async () => {
      malformedPractice = true
      await page.getByLabel('分析批次', { exact: true }).selectOption(newId)
      await page.getByRole('alert').filter({ hasText: '实践摘要或建议引用格式不符' }).waitFor()
      assert.equal(await page.locator('[data-batch-id]').getAttribute('data-batch-id'), oldId)
      assert.equal(await page.locator('[data-practice-batch]').count(), 0)
      malformedPractice = false
      await page.getByRole('button', { name: '重试请求', exact: true }).click()
      await page.locator(`[data-practice-batch="${newId}"]`).waitFor()
    })
    await check('未知版本明确拒绝并保留上一完整结果', async () => {
      unsupported = true
      await page.getByRole('button', { name: '刷新批次', exact: true }).click()
      await page.getByRole('alert').filter({ hasText: '暂不支持' }).waitFor()
      assert.equal(await page.locator('[data-practice-batch]').getAttribute('data-practice-batch'), newId)
      unsupported = false
      await page.getByRole('button', { name: '重试请求', exact: true }).click()
      await page.getByRole('alert').waitFor({ state: 'hidden' })
    })
    await check('采纳前审阅真实表单字段；失败重试保留原request和payload', async () => {
      await page.getByRole('button', { name: '审阅并采纳建议', exact: true }).click()
      await page.getByLabel('本人项目', { exact: true }).locator('option').waitFor({ state: 'attached' })
      assert.equal(await page.getByRole('button', { name: '采纳并创建一次任务', exact: true }).isDisabled(), true)
      await page.getByLabel('任务标题', { exact: true }).fill('本人审阅后的零分钟自测')
      await page.getByLabel('计划日期', { exact: true }).fill('2026-10-27')
      await page.getByRole('checkbox', { name: '我已审阅标题、日期、项目和建议来源，选择创建这项自测任务。' }).check()
      await page.getByRole('button', { name: '采纳并创建一次任务', exact: true }).click()
      await page.getByRole('alert').filter({ hasText: '首次响应失败' }).waitFor()
      assert.equal(await page.getByLabel('任务标题', { exact: true }).isDisabled(), true)
      await page.getByRole('button', { name: '重试原请求', exact: true }).click()
      await page.getByText('查看任务及来源', { exact: true }).waitFor()
      assert.equal(applications.length, 2)
      assert.deepEqual(applications[0], applications[1])
      assert.equal(applications[1].expected_rule_version, 'B-R1-advisory-1.0')
      assert.equal(applications[1].expected_session_revision, 9)
    })
    await check('任务可从id独立定位，并返回批次和实践历史', async () => {
      await page.getByText('查看任务及来源', { exact: true }).click()
      await page.locator('[data-located-task="901"]').waitFor()
      assert.ok((await page.locator('[data-located-task="901"]').innerText()).includes('本人审阅后的零分钟自测'))
      assert.equal(await page.locator('[data-located-task="901"]').getByRole('link').count(), 2)
      await page.locator('[data-located-task="901"]').getByText('返回分析批次与建议来源', { exact: true }).click()
      await page.locator(`[data-practice-batch="${newId}"]`).waitFor()
    })
    await check('定位来源卡随编辑和完成读取服务端结果，删除失败保留原卡', async () => {
      await page.goto(`${url}/learning/tasks?task_id=901`)
      await page.locator('[data-located-task="901"]').waitFor()
      await page.locator('.learning-task-board > li').first().getByRole('button', { name: '编辑', exact: true }).click()
      await page.getByLabel('任务标题', { exact: true }).fill('编辑后的来源任务')
      await page.getByRole('button', { name: '保存任务', exact: true }).click()
      await page.locator('[data-located-task="901"] h2').filter({ hasText: '编辑后的来源任务（服务端结果）' }).waitFor()
      assert.equal(await page.locator('[data-located-task="901"] h2').innerText(), '编辑后的来源任务（服务端结果）')
      await page.setViewportSize({ width: 390, height: 844 })
      await page.locator('[data-located-task="901"]').screenshot({ path: path.join(output, 'located-edited-390.png') }); result.screenshots.push('located-edited-390.png')
      await page.locator('.learning-task-board > li').first().getByRole('button', { name: '完成', exact: true }).click()
      await page.locator('[data-located-task="901"]').getByText('2026-10-27 · S10 Mock CSV实践项目 · 已完成', { exact: true }).waitFor()
      await page.getByText('任务已完成，计划进度已同步', { exact: true }).waitFor()
      await page.waitForFunction(() => document.querySelectorAll('.el-message').length === 0)
      await page.locator('[data-located-task="901"]').evaluate(element => {
        window.scrollBy(0, element.getBoundingClientRect().top - 104)
      })
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
      const completedCard = await page.locator('[data-located-task="901"]').boundingBox()
      assert.ok(completedCard && completedCard.y >= 96 && completedCard.y + completedCard.height <= 844 - 72, '完成后的定位卡必须完整处于固定页头与底栏之间')
      await page.locator('[data-located-task="901"]').screenshot({ path: path.join(output, 'located-completed-390.png') }); result.screenshots.push('located-completed-390.png')
      await page.setViewportSize({ width: 1440, height: 1050 })
      await page.locator('.learning-task-board > li').first().getByRole('button', { name: '删除', exact: true }).click()
      await page.getByRole('button', { name: '确认删除', exact: true }).click()
      await page.getByText('Mock：映射任务不可删除', { exact: true }).waitFor()
      assert.equal(await page.locator('[data-located-task="901"]').count(), 1)
    })
    await check('编辑等待期间切换定位任务，晚返回不会覆盖新卡', async () => {
      let arrived, release
      const entered = new Promise(resolve => { arrived = resolve })
      heldTaskEdit = { entered: arrived, promise: new Promise(resolve => { release = resolve }) }
      await page.locator('.learning-task-board > li').first().getByRole('button', { name: '编辑', exact: true }).click()
      await page.getByLabel('任务标题', { exact: true }).fill('切换任务前的延迟编辑')
      await page.getByRole('button', { name: '保存任务', exact: true }).click()
      await entered
      await page.evaluate(() => document.querySelector('#app').__vue_app__.config.globalProperties.$router.replace({ path: '/learning/tasks', query: { task_id: '902' } }))
      await page.locator('[data-located-task="902"]').waitFor()
      release()
      await page.getByRole('button', { name: '保存任务', exact: true }).waitFor({ state: 'hidden' })
      assert.equal(await page.locator('[data-located-task="902"] h2').innerText(), ordinaryTask.title)
      assert.equal(await page.locator('[data-located-task="901"]').count(), 0)
    })
    await check('普通任务成功删除后清空定位卡；没有真实DELETE', async () => {
      await page.locator('.learning-task-board > li').filter({ hasText: ordinaryTask.title }).getByRole('button', { name: '删除', exact: true }).click()
      await page.getByRole('button', { name: '确认删除', exact: true }).click()
      await page.locator('[data-located-task="902"]').waitFor({ state: 'hidden' })
      assert.equal(ordinaryDeleted, true)
      assert.equal(await page.locator('[data-located-task]').count(), 0)
    })
    await check('编辑等待期间换号，晚返回不会恢复前账号定位卡', async () => {
      await page.evaluate(() => document.querySelector('#app').__vue_app__.config.globalProperties.$router.replace({ path: '/learning/tasks', query: { task_id: '901' } }))
      await page.locator('[data-located-task="901"]').waitFor()
      let arrived, release
      const entered = new Promise(resolve => { arrived = resolve })
      heldTaskEdit = { entered: arrived, promise: new Promise(resolve => { release = resolve }) }
      await page.locator('.learning-task-board > li').first().getByRole('button', { name: '编辑', exact: true }).click()
      await page.getByLabel('任务标题', { exact: true }).fill('账号切换前的延迟编辑')
      await page.getByRole('button', { name: '保存任务', exact: true }).click()
      await entered
      await page.evaluate(() => {
        const auth = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('auth')
        sessionStorage.setItem('scholarhub.access_token', 's10-mock-other')
        auth.token = 's10-mock-other'; auth.currentUser = { ...auth.currentUser, id: 4 }
      })
      await page.locator('[data-located-task="901"]').waitFor({ state: 'hidden' })
      release()
      await page.getByRole('button', { name: '保存任务', exact: true }).waitFor({ state: 'hidden' })
      assert.equal(await page.locator('[data-located-task]').count(), 0)
      await page.goto(`${url}/offline-analytics?dataset_kind=controlled&batch_id=${newId}`)
      await page.locator(`[data-practice-batch="${newId}"]`).waitFor()
    })
    await check('桌面与390px阅读顺序、长引用和横向溢出', async () => {
      await page.locator('[data-practice-batch]').scrollIntoViewIfNeeded()
      await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true }); result.screenshots.push('desktop.png')
      await page.locator('[data-practice-batch]').screenshot({ path: path.join(output, 'practice-desktop.png') }); result.screenshots.push('practice-desktop.png')
      await page.setViewportSize({ width: 390, height: 844 })
      await page.getByText('逐会话核对提交与来源（4）', { exact: true }).click()
      await page.getByText('核对建议原始引用与批次', { exact: true }).click()
      await page.locator('[data-practice-batch]').scrollIntoViewIfNeeded()
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.screenshot({ path: path.join(output, 'mobile-390.png'), fullPage: true }); result.screenshots.push('mobile-390.png')
      await page.getByRole('button', { name: '审阅并采纳建议', exact: true }).click()
      await page.getByLabel('本人项目', { exact: true }).locator('option').waitFor({ state: 'attached' })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.locator('[aria-label="审阅并采纳建议"]').screenshot({ path: path.join(output, 'mobile-confirmation.png') }); result.screenshots.push('mobile-confirmation.png')
    })
    assert.deepEqual(errors, [])
    result.passed = true; result.api_calls = calls; save()
    console.log(JSON.stringify({ passed: true, checks: checks.length, mode: 'mock', database_writes: 0, real_model_calls: 0 }))
  } catch (cause) { result.page_text_at_failure = await activePage?.locator('body').innerText(); save(); throw cause } finally { await browser.close() }
}
async function realMain() {
  // 由主线程提供本轮已授权的已发布批次；不读取凭证文件，不调用Provider。
  assert.ok(process.env.S10_REAL_BATCH_FILE, '需要本轮真实批次输入文件')
  assert.ok(process.env.S10_TEST_TOKEN, '需要本轮隔离身份的内存Token')
  const input = JSON.parse(fs.readFileSync(process.env.S10_REAL_BATCH_FILE, 'utf8'))
  assert.ok(/^[\da-f-]{36}$/i.test(input.batch_id))
  assert.equal(typeof input.application_title, 'string')
  assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(input.scheduled_date))
  const realOutput = path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2/S10-证据/frontend-real')
  fs.mkdirSync(realOutput, { recursive: true })
  const evidence = { mode: 'real-api-isolated-mysql', model: 'existing-fake-events;no-model-request', checks: [], http: [], screenshots: [] }
  const persist = () => fs.writeFileSync(path.join(realOutput, 'results.json'), JSON.stringify(evidence, null, 2))
  const record = async (name, run) => { await run(); evidence.checks.push({ name, passed: true }); persist() }
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' })
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' })
    await context.addInitScript(token => { sessionStorage.setItem('scholarhub.access_token', token) }, process.env.S10_TEST_TOKEN)
    const page = await context.newPage(); page.setDefaultTimeout(15000)
    page.on('pageerror', cause => { evidence.page_errors ??= []; evidence.page_errors.push(cause.message) })
    page.on('response', response => {
      const endpoint = new URL(response.url())
      if (endpoint.pathname.startsWith('/api/v1/')) evidence.http.push({ method: response.request().method(), path: endpoint.pathname, status: response.status() })
    })
    const batchPromise = page.waitForResponse(response => new URL(response.url()).pathname === `/api/v1/offline-analytics/batches/${input.batch_id}`)
    await page.goto(`${url}/offline-analytics?dataset_kind=${input.dataset_kind || 'controlled'}&batch_id=${input.batch_id}`)
    const response = await batchPromise, batch = await response.json()
    const selectedCandidate = input.candidate_key
      ? batch.recommendations.find(item => item.candidate_key === input.candidate_key)
      : batch.recommendations[0]
    assert.ok(selectedCandidate, '指定候选必须属于本轮已发布批次')
    // 按同一响应中的候选位置定位，并在动作前核对属性，避免相同标题串候选。
    const candidateIndex = batch.recommendations.findIndex(item => item.candidate_key === selectedCandidate.candidate_key)
    const selectedRow = page.locator('[data-candidate]').nth(candidateIndex)
    await record('真实新版详情与原教学图同批展示', async () => {
      assert.equal(response.status(), 200)
      assert.equal(batch.schema_version, 'scholarhub-source-2.0')
      await page.locator(`[data-practice-batch="${input.batch_id}"]`).waitFor()
      assert.equal(await page.locator('.offline-figure').count(), 4)
      await page.locator('[data-practice-action-chart] canvas').waitFor()
      const values = await page.locator('[data-practice-action-chart] .analytics-chart-wrap').evaluate(element => element.__vueParentComponent.props.option.series[0].data)
      const practice = batch.topic_summary.practice
      assert.deepEqual(values, [practice.submission_event_count, practice.request_count, practice.personal_end_count, practice.cancel_count, practice.resume_count])
      const rows = await page.locator('.offline-practice-measures > div').allTextContents()
      assert.ok(rows.some(row => row.includes('实践会话') && row.includes(String(batch.topic_summary.practice.session_count))))
      assert.ok(batch.recommendations.length > 0)
    })
    await record('真实批次候选与绑定引用可定位', async () => {
      const item = selectedRow
      assert.equal(await item.getAttribute('data-candidate'), selectedCandidate.candidate_key)
      await item.getByText('核对建议原始引用与批次', { exact: true }).click()
      assert.equal(await item.locator('.offline-advice-references li').count(), selectedCandidate.references.length)
      await page.locator('[data-practice-batch]').screenshot({ path: path.join(realOutput, 'practice-desktop.png') }); evidence.screenshots.push('practice-desktop.png')
    })
    await record('真实旧批次兼容且混合列表保持可选', async () => {
      if (!input.legacy_batch_id) return
      await page.getByLabel('分析批次', { exact: true }).selectOption(input.legacy_batch_id)
      await page.locator(`[data-batch-id="${input.legacy_batch_id}"]`).waitFor()
      assert.equal(await page.locator('[data-practice-batch]').count(), 0)
      assert.equal(await page.locator('[data-rule]').count(), 5)
      await page.getByLabel('分析批次', { exact: true }).selectOption(input.batch_id)
      await page.locator(`[data-practice-batch="${input.batch_id}"]`).waitFor()
    })
    let application
    await record('本人审阅后通过真实应用API创建一次任务', async () => {
      await selectedRow.getByRole('button', { name: '审阅并采纳建议', exact: true }).click()
      await page.getByLabel('本人项目', { exact: true }).locator('option').first().waitFor({ state: 'attached' })
      await page.getByLabel('任务标题', { exact: true }).fill(input.application_title)
      await page.getByLabel('计划日期', { exact: true }).fill(input.scheduled_date)
      if (input.project_id) await page.getByLabel('本人项目', { exact: true }).selectOption(String(input.project_id))
      await page.getByRole('checkbox', { name: '我已审阅标题、日期、项目和建议来源，选择创建这项自测任务。' }).check()
      await page.setViewportSize({ width: 390, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.locator('[aria-label="审阅并采纳建议"]').screenshot({ path: path.join(realOutput, 'confirmation-390.png') }); evidence.screenshots.push('confirmation-390.png')
      const created = page.waitForResponse(res => new URL(res.url()).pathname.endsWith('/recommendation-applications') && res.request().method() === 'POST')
      await page.getByRole('button', { name: '采纳并创建一次任务', exact: true }).click()
      const res = await created; application = await res.json()
      assert.ok([200, 201].includes(res.status()), `应用HTTP ${res.status()}`)
      assert.ok(Number.isSafeInteger(application.task_id))
      evidence.application = application
      await page.getByText('查看任务及来源', { exact: true }).waitFor()
    })
    await record('真实任务详情可反查批次与实践来源', async () => {
      await page.getByText('查看任务及来源', { exact: true }).click()
      await page.locator(`[data-located-task="${application.task_id}"]`).waitFor()
      const located = page.locator(`[data-located-task="${application.task_id}"]`)
      assert.ok((await located.innerText()).includes(input.application_title))
      assert.equal(await located.getByRole('link').count(), 2)
      await located.screenshot({ path: path.join(realOutput, 'task-source-390.png') }); evidence.screenshots.push('task-source-390.png')
      await located.getByText('返回分析批次与建议来源', { exact: true }).click()
      await page.locator(`[data-practice-batch="${input.batch_id}"]`).waitFor()
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
      await page.locator('[data-practice-batch]').screenshot({ path: path.join(realOutput, 'practice-390.png') }); evidence.screenshots.push('practice-390.png')
    })
    assert.deepEqual(evidence.page_errors || [], [])
    assert.equal(evidence.http.filter(item => item.method === 'POST' && item.path.endsWith('/recommendation-applications')).length, 1)
    evidence.passed = true; persist()
    console.log(JSON.stringify({ passed: true, checks: evidence.checks.length, batch_id: input.batch_id, task_id: application.task_id }))
  } catch (cause) { evidence.passed = false; evidence.failure = cause.message; persist(); throw cause } finally { await browser.close() }
}

if (process.argv[2] === 'real') realMain().catch(cause => { console.error(cause); process.exitCode = 1 })
else main().catch(cause => { result.passed = false; result.failure = cause.message; save(); console.error(cause); process.exitCode = 1 })
