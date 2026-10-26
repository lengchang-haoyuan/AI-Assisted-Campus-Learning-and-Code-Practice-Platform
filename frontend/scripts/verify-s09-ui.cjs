// S09浏览器验收：Mock交互与隔离MySQL/Fake API分开记录。禁止收费调用。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { randomUUID } = require('node:crypto')
const { chromium } = require('playwright')
const root = path.resolve(__dirname, '../..')
const mode = process.argv[2] || 'mock'
const resumeTail = mode === 'real' && process.env.S09_TAIL_ONLY === '1'
assert(['mock', 'real', 'restart'].includes(mode))
const output = path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2/S09-证据', mode)
const url = 'http://127.0.0.1:4197'
const api = 'http://127.0.0.1:56593/api/v1'
const template = JSON.parse(execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-B', '-X', 'utf8', '-c', 'import json; from app.practice.templates import get_template; print(json.dumps(get_template(),ensure_ascii=False))'], { cwd: path.join(root, 'backend'), encoding: 'utf8' }))
const now = new Date().toISOString()
const project = id => ({ id, name: `S09 ${mode} 步骤式实践`, description: '用 CSV 练习逐行校验与统计，保留自己的提交过程。', difficulty: 'beginner', status: 'not_started', tags: [], language: 'Python', framework: null, frontend: null, backend: null, database: null, requirements: [], output_requirement: '提交纯函数及可选的自测记录', progress: 0, created_at: now, updated_at: now })
const values = id => ({ project_name: project(id).name, difficulty: 'beginner', language: 'Python', framework: null, frontend: null, backend: null, database: null, requirements: [], output_requirement: project(id).output_requirement, architecture: null, features: [], constraints: [], extensions: {} })
const ctx = id => ({ project_id: id, version: 1, values: values(id), field_metadata: {}, updated_at: now, source: { type: 'project', id, node_key: null }, is_stale: false, stale_fields: [], stale_node_ids: [] })
const clone = value => JSON.parse(JSON.stringify(value))
const findings = [], calls = [], errors = []
const evidence = { mode, model: 'fake', real_model_calls: 0, checks: findings, errors, screenshots: [] }
const check = async (name, task) => {
  evidence.current_check = name
  fs.writeFileSync(path.join(output, 'progress.json'), JSON.stringify({ current_check: name, completed: findings, recent_calls: calls.slice(-8) }, null, 2))
  await task(); findings.push({ name, passed: true })
}
const code1 = '# S09 version 1\ndef summarize_records(csv_text: str) -> dict:\n    return {}\n'
const code2 = '# S09 version 2\ndef summarize_records(csv_text: str) -> dict:\n    return {"record_count": 0}\n'

async function installMock(page) {
  const contexts = { 701: ctx(701), 702: ctx(702) }, sessions = new Map()
  let conflict = false, heldReview = null, releaseReview, heldContext = null, candidateMode = false
  const goals = {}
  const response = (route, data, status = 200) => route.fulfill({ status, json: clone(data) })
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), pathname = new URL(req.url()).pathname.replace('/api/v1', ''), body = req.postDataJSON()
    calls.push({ path: pathname, method: req.method(), action: body?.action })
    if (pathname === '/users/me') return response(route, { id: 3, username: 's09_fixture', email: 's09@example.invalid', is_active: true, created_at: now })
    if (pathname === '/campus/me') return response(route, { membership: null })
    const workflow = { id: 999, name: 'Mock候选来源', project: { id: 701, name: project(701).name }, version: 1 }
    if (pathname === '/workflows') return response(route, { items: candidateMode ? [workflow] : [], total: candidateMode ? 1 : 0, page: 1, page_size: 20, total_pages: candidateMode ? 1 : 0 })
    if (pathname === '/workflows/999/graph') return response(route, { workflow, edges: [], nodes: [{ id: 9991, workflow_id: 999, node_key: 'requirements', node_type: 'requirements_analysis', status: 'success', context_version: contexts[701].version, config: { context_writes: ['features'] } }] })
    if (pathname === '/workflows/999/runs') return response(route, { items: [{ id: 9992, workflow_id: 999, status: 'completed', context_version: contexts[701].version, nodes: [{ node_id: 9991, node_key: 'requirements', node_type: 'requirements_analysis', request_id: 9993, status: 'completed', result: { result_type: 'requirements_analysis', summary: 'Mock候选，仅验证批准交互', features: ['自行批准的功能候选'], constraints: [], requirements: [{ title: '候选需求', description: '仅测试数据', acceptance_criteria: ['手动选择'] }] } }] }], total_pages: 1 })
    if (pathname === '/workflows/999/nodes/9991/context/write') {
      assert.equal(body.expected_version, contexts[701].version); assert.deepEqual(Object.keys(body.values), ['features'])
      contexts[701].values.features = body.values.features; contexts[701].version++
      return response(route, { context: contexts[701], changed_fields: ['features'], stale_node_ids: [] })
    }
    const p = pathname.match(/^\/projects\/(\d+)(?:\/(.*))?$/)
    if (p) {
      const id = Number(p[1]), tail = p[2]
      if (!tail) return response(route, { ...project(id), ...contexts[id].values, description: goals[id] ?? project(id).description, name: contexts[id].values.project_name })
      if (tail === 'context') {
        if (req.method() === 'GET') {
          if (heldContext?.id === id) { const gate = heldContext; heldContext = null; gate.entered(); await gate.promise }
          return response(route, contexts[id])
        }
        if (conflict) { conflict = false; contexts[id].version++; contexts[id].values.output_requirement = '另一个窗口的交付要求'; return response(route, { error: { message: '版本冲突' } }, 409) }
        Object.assign(contexts[id].values, body.values); contexts[id].version++
        return response(route, { context: contexts[id], changed_fields: Object.keys(body.values), stale_node_ids: [] })
      }
      if (tail === 'practice-sessions') {
        if (req.method() === 'GET') return response(route, [...sessions.values()].filter(item => item.project_id === id).reverse())
        const item = { id: randomUUID(), owner_user_id: 3, project_id: id, template_id: template.template_id, template_version: '1.0', context_version: contexts[id].version, context_snapshot: { version: contexts[id].version, values: contexts[id].values }, current_step_key: 'understand', status: 'ready', revision: 1, template, attempts: [], current_attempt: null, outputs: {}, active_result: null, active_action: null, model_request: null, created_at: now, updated_at: now }
        sessions.set(item.id, item); return response(route, item, 201)
      }
    }
    const match = pathname.match(/^\/practice-sessions\/([^/]+)(?:\/(actions|attempts))?$/)
    if (match) {
      const item = sessions.get(match[1]); assert(item)
      if (!match[2]) return response(route, item)
      if (body.expected_revision !== item.revision) return response(route, { error: { message: '版本已变化' } }, 409)
      if (match[2] === 'attempts') {
        item.attempts.forEach(a => { a.is_current = false; a.can_confirm = false; a.candidate_stale = true })
        const attempt = { id: randomUUID(), attempt_no: item.attempts.length + 1, step_key: 'implement', status: 'submitted', code: body.code, declared_output: body.declared_output, self_statement: body.self_statement, is_current: true, candidate_stale: false, can_confirm: true, operation_id: null, ai_request_id: null, created_at: now, reviewed_at: null }
        attempt.feedback = { schema_version: 'practice-feedback/1.0', binding: { attempt_id: attempt.id, attempt_no: attempt.attempt_no, template_version: '1.0', context_version: item.context_version, submitted_revision: item.revision + 1 }, self_statement: { source: 'student_declaration', value: body.self_statement }, submitted_output_match: { source: 'server_fixed_value_comparison', matched: false, checks: template.public_output_vectors.map(v => ({ test_id: v.test_id, matched: false })), code_executed: false }, ai_static_review: null, personal_confirmation: null, teacher_confirmation: null }
        item.attempts.push(attempt); item.current_attempt = attempt; item.status = 'waiting_confirmation'; item.active_result = item.model_request = null; item.revision++
        return response(route, item, 201)
      }
      const action = body.action
      if (action === 'cancel') item.status = 'cancelled'
      else if (action === 'resume') item.status = item.current_attempt ? 'waiting_confirmation' : item.current_step_key === 'understand' ? 'ready' : 'waiting_submission'
      else if (action === 'confirm') {
        if (item.current_step_key === 'understand') { item.current_step_key = 'implement'; item.status = 'waiting_submission' }
        else { item.status = 'completed'; item.current_attempt.can_confirm = false; item.current_attempt.feedback.personal_confirmation = { source: 'student_review_confirmation', actor_user_id: 3, confirmed_at: now, ai_request_id: item.current_attempt.ai_request_id, criteria: [] } }
      } else {
        item.model_request = { id: calls.length, provider: 'fake', model: 'fake-s09', status: 'completed', prompt_tokens: 10, completion_tokens: 10, error_code: null }
        if (action === 'review') {
          if (item.current_attempt.code.includes('FAIL_ADVICE')) { item.status = 'failed'; item.model_request.status = 'failed'; item.model_request.error_code = 'upstream_error'; item.current_attempt.feedback.review_error = { source: 'ai_static_review', code: 'upstream_error', ai_request_id: item.model_request.id } }
          else {
            const review = { summary: 'Fake：返回字段可进一步自查。', overall: 'needs_changes', criteria: template.criteria.map(c => ({ criterion_id: c.criterion_id, verdict: 'unknown', reason: 'Fake 工程样例；信息不足，建议自行核对。', issue_type: null, evidence_span: null, suggested_self_test: '核对公开输入和五字段', next_action: '自行决定是否修改' })) }
            item.current_attempt.feedback.ai_static_review = { source: 'ai_static_review', ai_request_id: item.model_request.id, operation_id: randomUUID(), review, code_executed: false }; item.current_attempt.ai_request_id = item.model_request.id
          }
          if (item.current_attempt.code.includes('HOLD_ADVICE')) {
            const late = clone(item); item.status = 'running'; item.revision++
            heldReview = new Promise(resolve => { releaseReview = resolve })
            await heldReview; return response(route, late)
          }
        } else { item.active_result = { summary: 'Fake 工程说明', guidance: ['逐行区分未知分钟和已知零'], checks: ['核对公开 T01/T04'] }; item.outputs.understand = item.active_result; item.status = 'waiting_confirmation' }
      }
      item.revision++; return response(route, item)
    }
    throw new Error(`unexpected_mock_endpoint:${req.method()}:${pathname}`)
  })
  return { contexts, sessions, goal: (id, value) => { goals[id] = value }, conflict: () => { conflict = true }, release: () => releaseReview?.(), held: () => Boolean(heldReview), candidates: () => { candidateMode = true }, holdContext: id => { let release, entered; const promise = new Promise(resolve => { release = resolve }), ready = new Promise(resolve => { entered = resolve }); heldContext = { id, promise, entered }; return { release, ready } } }
}

async function main() {
  fs.mkdirSync(output, { recursive: true })
  if (fs.existsSync(path.join(output, 'results.json')) && mode === 'mock') {
    let previous = 1
    while (fs.existsSync(path.join(output, `results-attempt-${previous}.json`))) previous++
    fs.copyFileSync(path.join(output, 'results.json'), path.join(output, `results-attempt-${previous}.json`))
  }
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' })
  const deadline = setTimeout(() => {
    evidence.passed = false; evidence.failure = `浏览器脚本超时：${evidence.current_check}`
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(evidence, null, 2))
    browser.close().finally(() => process.exit(1))
  }, 180000)
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] })
    const page = await context.newPage()
    page.on('pageerror', e => errors.push(e.message))
    page.on('dialog', d => d.accept())
    await page.addInitScript(token => { sessionStorage.setItem('scholarhub.access_token', token) }, mode === 'mock' ? 's09-mock' : process.env.S09_TOKEN)
    const mock = mode === 'mock' ? await installMock(page) : null
    let projectId = mode === 'mock' ? 701 : Number(process.env.S09_PROJECT)
    assert(Number.isSafeInteger(projectId))
    const goto = async target => { await page.goto(url + target); await page.getByRole('heading', { name: /项目准备|实践工作台/ }).waitFor() }
    const requestCount = () => calls.filter(c => ['start', 'hint', 'review', 'explain', 'continue'].includes(c.action)).length
    const screenshot = async name => {
      const file = path.join(output, name); await page.evaluate(() => scrollTo(0, 0))
      await page.screenshot({ path: file, fullPage: true }); evidence.screenshots.push(file)
      await page.screenshot({ path: file.replace('.png', '-viewport.png') })
    }
    const overflow = async () => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'horizontal_overflow')
    const currentSession = async () => {
      const id = new URL(page.url()).searchParams.get('session')
      assert(id)
      return id
    }
    const newPractice = async () => {
      await page.getByRole('button', { name: '创建新实践', exact: true }).click()
      await page.getByRole('button', { name: '请求本步 AI 说明', exact: true }).waitFor()
      await page.getByRole('button', { name: '请求本步 AI 说明', exact: true }).click()
      await page.getByRole('checkbox', { name: '我已阅读本次任务说明，准备自行实现' }).check()
      await page.getByRole('button', { name: '已阅读，开始实现', exact: true }).click()
      await page.getByRole('button', { name: '填写代码提交', exact: true }).waitFor()
      return currentSession()
    }
    const submit = async code => {
      await page.getByRole('button', { name: /填写代码提交|修改并追加新版本/ }).click()
      await page.getByRole('textbox', { name: '函数代码 · 最多 12000 字符' }).fill(code)
      await page.getByRole('button', { name: '保存为新的提交', exact: true }).click()
      await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).waitFor()
    }
    const finish = async () => { await page.getByRole('checkbox', { name: /我已审阅当前提交/ }).check(); await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).click(); await page.getByText('本人已审阅，本次实践已结束。可以查看和复制历史提交。', { exact: true }).waitFor() }
    if (mode === 'restart') {
      const result = JSON.parse(fs.readFileSync(path.join(output, '../real/results.json'), 'utf8'))
      await goto(`/projects/${projectId}/practice?session=${result.restore_session}`)
      await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).waitFor()
      assert.equal(await page.getByLabel('所选提交代码').textContent(), code2)
      findings.push({ name: '服务进程重启后读取同一当前attempt/安全等待点', passed: true })
      await screenshot('restart-restored.png'); await overflow()
    } else {
      if (resumeTail) {
        const priorPath = path.join(output, 'results.json'), prior = JSON.parse(fs.readFileSync(priorPath, 'utf8'))
        let suffix = 1
        while (fs.existsSync(path.join(output, `results-before-tail-${suffix}.json`))) suffix++
        fs.copyFileSync(priorPath, path.join(output, `results-before-tail-${suffix}.json`))
        findings.push(...prior.checks); evidence.screenshots.push(...prior.screenshots); evidence.restore_session = prior.restore_session
      }
      if (!resumeTail) {
      await check('项目准备：固定模板、已定技术、无需生成草案入口', async () => {
        await goto(`/projects/${projectId}/ai`)
        if (await page.getByRole('button', { name: '创建项目 Context', exact: true }).count()) await page.getByRole('button', { name: '创建项目 Context', exact: true }).click()
        await page.getByRole('link', { name: '进入步骤式实践', exact: true }).waitFor()
        assert.equal(await page.getByRole('link', { name: '在项目详情维护目标', exact: true }).getAttribute('href'), `/projects/${projectId}`)
        await page.getByText('本人已定技术', { exact: true }).waitFor(); await screenshot('preparation-desktop.png'); await overflow()
        await page.setViewportSize({ width: 390, height: 844 }); await screenshot('preparation-390.png'); await overflow(); await page.setViewportSize({ width: 1440, height: 1000 })
      })
      if (mock) await check('目标维护入口与刷新保留当前资料草稿', async () => {
        await page.getByRole('textbox', { name: '交付要求', exact: true }).fill('本页需要保留的草稿')
        mock.goal(701, '在项目详情保存后的新目标')
        await page.getByRole('button', { name: '刷新目标与资料', exact: true }).click()
        await page.getByText('在项目详情保存后的新目标', { exact: true }).waitFor()
        assert.equal(await page.getByRole('textbox', { name: '交付要求', exact: true }).inputValue(), '本页需要保留的草稿')
      })
      if (mock) await check('保存冲突保留草稿、读取最新后合并、不串项目', async () => {
        await page.getByRole('textbox', { name: '交付要求', exact: true }).fill('本页需要保留的草稿')
        mock.conflict(); await page.getByRole('button', { name: '保存 Context v1', exact: true }).click()
        await page.getByText(/你的草稿仍保留/).waitFor()
        await page.getByRole('button', { name: '载入最新版本，保留草稿', exact: true }).click()
        assert.equal(await page.getByRole('textbox', { name: '交付要求', exact: true }).inputValue(), '本页需要保留的草稿')
        await page.getByRole('button', { name: '保存 Context v2', exact: true }).click()
        await page.getByRole('link', { name: '进入步骤式实践', exact: true }).waitFor()
      })
      await page.getByRole('link', { name: '进入步骤式实践', exact: true }).click()
      await check('首次提交后直接本人结束，不请求implement建议', async () => {
        const before = requestCount()
        if (process.env.S09_RESUME_FIRST_SESSION && mode === 'real') {
          await goto(`/projects/${projectId}/practice?session=${process.env.S09_RESUME_FIRST_SESSION}`)
          await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).waitFor()
          assert.equal(await page.getByLabel('所选提交代码').textContent(), code1)
        } else { await newPractice(); await submit(code1) }
        assert.equal(await page.getByText('未提供正式教师确认', { exact: true }).count(), 1); await finish(); if (mock) assert.equal(requestCount(), before + 1)
      })
      await check('建议后自选修改、不可覆盖历史、复制绑定所选版本', async () => {
        await newPractice(); await submit(code1)
        await page.getByRole('button', { name: '获取当前提交的 AI 建议', exact: true }).click()
        await page.getByText(/Fake.*返回字段|Fake.*工程建议/).first().waitFor()
        // needs_changes仍能直接结束，用户自行选择修改。
        assert(await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).isVisible())
        await submit(code2)
        const select = page.getByRole('combobox', { name: '查看提交版本', exact: true })
        const options = await select.locator('option').evaluateAll(items => items.map(i => i.value))
        assert.equal(options.length, 2); await select.selectOption(options[0])
        await page.getByRole('button', { name: '复制所选提交的代码', exact: true }).click()
        assert.equal((await page.evaluate(() => navigator.clipboard.readText())).replaceAll('\r\n', '\n'), code1)
        assert.equal(await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).count(), 0)
        await select.selectOption(options[1]); assert.equal(await page.getByLabel('所选提交代码').textContent(), code2)
        await screenshot('workbench-desktop.png'); await overflow()
        await page.setViewportSize({ width: 390, height: 844 }); await screenshot('workbench-390.png'); await overflow()
        await page.setViewportSize({ width: 1440, height: 1000 }); await finish()
      })
      await check('无提交继续等待，取消后恢复不自动调用模型', async () => {
        await newPractice(); assert.equal(await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).count(), 0)
        const before = requestCount(); await page.getByRole('button', { name: '取消本次会话', exact: true }).click()
        await page.getByRole('button', { name: '恢复安全等待', exact: true }).click()
        await page.getByRole('button', { name: '填写代码提交', exact: true }).waitFor(); if (mock) assert.equal(requestCount(), before)
      })
      await check('建议失败、恢复后本人结束', async () => {
        await submit(code1 + '# FAIL_ADVICE\n'); await page.getByRole('button', { name: '获取当前提交的 AI 建议', exact: true }).click()
        await page.getByText('AI 请求未完成', { exact: true }).first().waitFor()
        await page.getByRole('button', { name: '恢复安全等待', exact: true }).click(); await finish()
      })
      if (mock) await check('取消后迟到模型响应不覆盖恢复和新提交', async () => {
        await newPractice(); await submit(code1 + '# HOLD_ADVICE\n')
        await page.getByRole('button', { name: '获取当前提交的 AI 建议', exact: true }).click(); await page.waitForFunction(() => document.body.innerText.includes('请求已发送'))
        await page.getByRole('button', { name: '取消本次会话', exact: true }).click(); await page.getByRole('button', { name: '恢复安全等待', exact: true }).click()
        await submit(code2); assert(mock.held()); mock.release(); await page.waitForTimeout(250)
        assert.equal(await page.getByLabel('所选提交代码').textContent(), code2)
      })
      await check('刷新重入保留当前attempt与等待点', async () => {
        await newPractice(); await submit(code2); evidence.restore_session = await currentSession()
        await page.reload(); await page.getByRole('button', { name: '已审阅，结束本次实践', exact: true }).waitFor(); assert.equal(await page.getByLabel('所选提交代码').textContent(), code2)
      })
      if (mock) await check('长代码在390px内部滚动、控件具有键盘焦点', async () => {
        await submit(code2 + '# ' + '中文长行'.repeat(1000) + '\n')
        await page.setViewportSize({ width: 390, height: 844 }); await overflow()
        const block = page.getByLabel('所选提交代码')
        assert(await block.evaluate(item => item.scrollWidth > item.clientWidth))
        await block.focus(); assert(await block.evaluate(item => document.activeElement === item))
        await page.setViewportSize({ width: 1440, height: 1000 })
      })
      }
      if (mode === 'real') {
        if (!findings.some(item => item.name === '已有节点Context候选：来源差异、过期拒写、资料更新保留旧实践快照' && item.passed)) await check('已有节点Context候选：来源差异、过期拒写、资料更新保留旧实践快照', async () => {
          await goto(`/projects/${projectId}/ai`)
          await page.getByText('AI 候选与字段差异', { exact: true }).click()
          await page.getByRole('button', { name: '查询候选来源（不调用模型）', exact: true }).click()
          await page.getByRole('combobox', { name: '来源工作流', exact: true }).selectOption(process.env.S09_WORKFLOW)
          const choice = page.getByRole('combobox', { name: '确切历史请求', exact: true })
          await choice.locator('option').nth(1).waitFor({ state: 'attached' }); await choice.selectOption(await choice.locator('option').nth(1).getAttribute('value'))
          // 原引擎在run中已合并Context；旧run版本不足以重新批准候选，前端必须拒写。
          await page.getByText('该结果版本或节点状态已过期，仅供参考，不能写回当前资料。', { exact: true }).waitFor()
          assert(await page.getByRole('button', { name: '应用所选候选', exact: true }).isDisabled())
          await screenshot('candidate-readonly.png')
          await page.getByRole('textbox', { name: '核心功能', exact: true }).fill('本人补充：保留提交版本')
          await page.getByRole('button', { name: `保存 Context v${process.env.S09_CONTEXT_VERSION}`, exact: true }).click()
          await page.getByRole('link', { name: '进入步骤式实践', exact: true }).waitFor()
          await goto(`/projects/${projectId}/practice?session=${evidence.restore_session}`)
          await page.getByText(/本次实践使用资料 v\d+，项目最新为 v\d+/).waitFor()
          assert.equal(await page.getByLabel('所选提交代码').textContent(), code2)
        })
        await check('原高级画布及旧结果入口可读', async () => {
          await page.goto(`${url}/workflows/${process.env.S09_WORKFLOW}`)
          await page.getByRole('textbox', { name: '工作流名称', exact: true }).waitFor()
          assert.equal(await page.getByRole('textbox', { name: '工作流名称', exact: true }).inputValue(), 'S09旧工作流兼容Fake')
          await screenshot('legacy-canvas.png')
        })
      }
      if (mock) {
        await check('候选只应用明确勾选字段、原端点版本保护与防重复', async () => {
          mock.candidates(); await goto('/projects/701/ai')
          await page.getByText('AI 候选与字段差异', { exact: true }).click()
          await page.getByRole('button', { name: '查询候选来源（不调用模型）', exact: true }).click()
          await page.getByRole('combobox', { name: '来源工作流', exact: true }).selectOption('999')
          const choice = page.getByRole('combobox', { name: '确切历史请求', exact: true })
          await choice.locator('option').nth(1).waitFor({ state: 'attached' }); await choice.selectOption('9992:9993')
          assert(await page.getByRole('button', { name: '应用所选候选', exact: true }).isDisabled())
          await page.getByRole('checkbox', { name: '功能', exact: true }).check()
          await page.getByRole('checkbox', { name: '我已核对来源与差异，仅应用勾选字段', exact: true }).check()
          await page.getByRole('button', { name: '应用所选候选', exact: true }).click()
          await page.getByText(/已应用所选字段/).waitFor()
          assert.equal(calls.filter(c => c.path.endsWith('/context/write')).length, 1)
          assert.equal(await page.getByRole('textbox', { name: '核心功能', exact: true }).inputValue(), '自行批准的功能候选')
        })
        await check('快速切换项目后丢弃旧Context迟到响应', async () => {
          mock.contexts[702].values.project_name = '快速切换项目702'
          await goto('/projects/702/ai')
          const held = mock.holdContext(701)
          await page.evaluate(async () => { await document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/projects/701/ai') })
          try {
            await Promise.race([held.ready, new Promise((_, reject) => setTimeout(() => reject(new Error('旧项目Context屏障未进入')), 5000))])
            await page.evaluate(async () => { await document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/projects/702/ai') })
            await page.getByRole('textbox', { name: '项目名称', exact: true }).waitFor(); held.release(); await page.waitForTimeout(100)
            assert.equal(await page.getByRole('textbox', { name: '项目名称', exact: true }).inputValue(), '快速切换项目702')
          } finally { held.release() }
        })
        await check('错误项目的会话响应不渲染私有提交', async () => {
          await goto(`/projects/702/practice?session=${evidence.restore_session}`)
          await page.getByRole('alert').filter({ hasText: '实践加载失败，请检查权限后重试。' }).waitFor()
          assert.equal(await page.getByLabel('所选提交代码').count(), 0)
        })
      }
      if (mock) await check('退出账号清空私有页面、旧路由保留', async () => {
        await goto(`/projects/701/practice?session=${evidence.restore_session}`)
        await page.getByLabel('所选提交代码').waitFor()
        const routeModule = await page.evaluate(() => document.querySelector('#app').__vue_app__.config.globalProperties.$router.getRoutes().map(item => item.path))
        assert(routeModule.includes('/workflows/:id')); assert(routeModule.includes('/projects/:id/ai'))
        await page.evaluate(() => document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('auth').clearSession())
        await page.waitForFunction(() => !document.body.innerText.includes('# S09 version 2'))
      })
    }
    assert.equal(errors.length, 0, errors.join(';'))
    evidence.passed = true; evidence.mock_requests = mode === 'mock' ? calls : undefined
  } catch (e) { evidence.passed = false; evidence.failure = String(e.message); throw e }
  finally { clearTimeout(deadline); fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(evidence, null, 2)); await browser.close() }
}
main().catch(e => { console.error(e.message); process.exitCode = 1 })
