// 复用现有 Playwright；仅 HTTP Mock，无真实账号、数据库和模型调用。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4181'
const output = path.resolve(__dirname, '../../开发相关文档/测试证据/CR4')
const baselinePath = path.resolve(__dirname, '../src/.cr4-before.ts')
const now = '2026-10-16T04:00:00Z'
const empty = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
const task = title => ({ id: 21, title, status: 'pending', priority: 'medium',
  description: null, scheduled_date: '2026-10-16', plan: null, project: null,
  completed_at: null, start_time: null, end_time: null, estimated_minutes: 10,
  created_at: now, updated_at: now })
const taskPage = title => ({ ...empty, items: [task(title)], total: 1, total_pages: 1 })
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

async function main() {
  fs.mkdirSync(output, { recursive: true })
  assert(!fs.existsSync(baselinePath), '临时基线模块已存在，拒绝覆盖')
  // 固定修复前版本，避免提交后 HEAD 改变导致反例失效。
  const baseline = execFileSync('git', ['show', '3d459ad:frontend/src/stores/learning.ts'], {
    cwd: path.resolve(__dirname, '../..'), encoding: 'utf8',
  }).replace("defineStore('learning'", "defineStore('cr4_baseline'")
  fs.writeFileSync(baselinePath, baseline +
    "\nimport { createPinia } from 'pinia'\nexport const createBaselineStore = () => useLearningStore(createPinia())\n")
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  const deadline = setTimeout(async () => {
    console.error('CR4 browser deadline exceeded')
    await browser.close()
    if (fs.existsSync(baselinePath)) fs.unlinkSync(baselinePath)
    process.exit(1)
  }, 60000)
  try {
    const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(() => {
      if (!sessionStorage.getItem('cr4-seeded')) {
        sessionStorage.setItem('scholarhub.access_token', 'account-A')
        sessionStorage.setItem('cr4-seeded', 'yes')
      }
    })
    let holdTasks = false
    const taskWaiters = []
    const nextTask = () => {
      const gate = deferred(); taskWaiters.push(gate); return gate.promise
    }
    let held401 = null
    await page.route('**/api/v1/**', async route => {
      const request = route.request()
      const url = new URL(request.url())
      const endpoint = url.pathname.replace('/api/v1', '')
      const token = request.headers().authorization
      const respond = json => route.fulfill({ status: 200, json })
      if (endpoint === '/users/me') return respond({ id: token === 'Bearer account-B' ? 2 : 1,
        username: token === 'Bearer account-B' ? 'account_B' : 'account_A',
        email: 'fixture@example.invalid', avatar_url: null, bio: null, is_active: true, created_at: now })
      if (endpoint === '/campus/me') return respond({ membership: null })
      if (endpoint === '/auth/login') return respond({ access_token: 'account-B', token_type: 'bearer' })
      if (endpoint === '/auth/logout-all') return route.fulfill({ status: 204 })
      if (endpoint === '/cr4-old-401') {
        const gate = deferred(); held401.resolve(gate)
        await gate.promise
        return route.fulfill({ status: 401, json: { error: { message: 'expired fixture' } } })
      }
      if (endpoint === '/projects') {
        if (token === 'Bearer account-B') return route.fulfill({ status: 500, json: {} })
        return respond({ ...empty, total: 1, total_pages: 1, items: [{ id: 7,
          name: 'A_PRIVATE_PROJECT', description: 'A_PRIVATE_DESCRIPTION', difficulty: 'intermediate',
          status: 'in_progress', tags: [], language: 'Python', framework: 'FastAPI',
          frontend: 'Vue', backend: 'FastAPI', database: 'MySQL', created_at: now, updated_at: now }] })
      }
      if (endpoint === '/learning/tasks') {
        if (!holdTasks) return respond(taskPage('正常任务'))
        const gate = deferred()
        assert(taskWaiters.length, '缺少任务请求屏障')
        taskWaiters.shift().resolve(gate)
        const response = await gate.promise
        return route.fulfill(response)
      }
      return respond(empty)
    })
    await page.goto(`${baseUrl}/learning/tasks`)
    await page.getByText('正常任务', { exact: true }).waitFor()
    const findings = []
    for (const before of [true, false]) {
      await page.evaluate(async before => {
        const { pinia } = await import('/src/stores/index.ts')
        const module = await import(before ? '/src/.cr4-before.ts' : '/src/stores/learning.ts')
        window.cr4Store = before ? module.createBaselineStore() : module.useLearningStore(pinia)
      }, before)
      holdTasks = true
      for (const oldFails of [false, true]) {
        const first = nextTask()
        await page.evaluate(() => { window.cr4Old = window.cr4Store.fetchTasks({ page: 1, pageSize: 20 },
          { scheduledDate: '2026-10-16' }).catch(() => undefined) })
        const oldGate = await first
        const second = nextTask()
        await page.evaluate(() => { window.cr4New = window.cr4Store.fetchTasks({ page: 1, pageSize: 20 }).catch(() => undefined) })
        const newGate = await second
        newGate.resolve({ status: 200, json: taskPage('最新全部任务') })
        await page.evaluate(() => window.cr4New)
        oldGate.resolve(oldFails ? { status: 500, json: {} } : { status: 200, json: taskPage('过期今天任务') })
        await page.evaluate(() => window.cr4Old)
        const state = await page.evaluate(() => ({ title: window.cr4Store.taskPage.items[0]?.title,
          error: window.cr4Store.taskError, loading: window.cr4Store.loadingTasks }))
        const correct = state.title === '最新全部任务' && state.error === null && !state.loading
        findings.push({ baseline: before, oldFails, correct })
        assert.equal(correct, !before)
      }
      const first = nextTask()
      await page.evaluate(() => { window.cr4Old = window.cr4Store.fetchTasks({ page: 1, pageSize: 20 }) })
      const oldGate = await first
      const second = nextTask()
      await page.evaluate(() => { window.cr4New = window.cr4Store.fetchTasks({ page: 2, pageSize: 20 }) })
      const newGate = await second
      oldGate.resolve({ status: 200, json: taskPage('旧请求已结束') })
      await page.evaluate(() => window.cr4Old)
      assert.equal(await page.evaluate(() => window.cr4Store.loadingTasks), !before)
      newGate.resolve({ status: 200, json: taskPage('最新全部任务') })
      await page.evaluate(() => window.cr4New)
      holdTasks = false
    }
    holdTasks = true
    const oldFilter = nextTask()
    await page.getByRole('tab', { name: '全部任务', exact: true }).click()
    const oldFilterGate = await oldFilter
    const newFilter = nextTask()
    await page.getByRole('tab', { name: '今天', exact: true }).click()
    const newFilterGate = await newFilter
    newFilterGate.resolve({ status: 200, json: taskPage('最新今天任务') })
    await page.getByText('最新今天任务', { exact: true }).waitFor()
    const oldFilterResponse = page.waitForResponse(response => response.url().includes('/learning/tasks') &&
      !new URL(response.url()).searchParams.has('scheduled_date'))
    oldFilterGate.resolve({ status: 200, json: taskPage('过期全部任务') })
    await oldFilterResponse
    assert.equal(await page.getByRole('tab', { name: '今天', exact: true }).getAttribute('aria-selected'), 'true')
    assert.equal(await page.getByText('最新今天任务', { exact: true }).count(), 1)
    holdTasks = false
    await page.screenshot({ path: path.join(output, 'tasks-latest.png'), fullPage: true })
    held401 = deferred()
    await page.evaluate(async () => {
      const { apiClient } = await import('/src/api/client.ts')
      window.cr4Old401 = apiClient.get('/cr4-old-401').catch(() => undefined)
    })
    const old401 = await held401.promise
    await page.evaluate(() => sessionStorage.setItem('scholarhub.access_token', 'account-B'))
    old401.resolve()
    await page.evaluate(() => window.cr4Old401)
    assert.equal(await page.evaluate(() => sessionStorage.getItem('scholarhub.access_token')), 'account-B')
    await page.evaluate(() => sessionStorage.setItem('scholarhub.access_token', 'account-A'))
    await page.locator('a[href="/projects"]').first().click()
    await page.mouse.move(0, 0)
    try {
      await page.getByRole('link', { name: 'A_PRIVATE_PROJECT', exact: true }).waitFor({ timeout: 5000 })
    } catch (error) {
      console.error(JSON.stringify({ stage: 'account-A-cache', url: page.url(), body: (await page.locator('body').innerText()).slice(0, 1400) }))
      throw error
    }
    await page.locator('a[href="/profile"]').first().click()
    await page.evaluate(() => { window.cr4OldDocument = 'A' })
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: '撤销全部会话', exact: true }).click()
    await page.waitForURL('**/login?notice=*')
    await page.waitForLoadState('domcontentloaded')
    assert.equal(await page.evaluate(() => window.cr4OldDocument), undefined)
    await page.evaluate(async () => {
      const { useAuthStore } = await import('/src/stores/auth.ts')
      const { pinia } = await import('/src/stores/index.ts')
      await useAuthStore(pinia).login({ username: 'account_B', password: 'fictional-password' })
    })
    await page.goto(`${baseUrl}/projects`)
    await page.getByRole('alert').waitFor()
    assert.equal(await page.getByText('A_PRIVATE_PROJECT', { exact: true }).count(), 0)
    assert.equal(await page.evaluate(async () => {
      const { useLearningStore } = await import('/src/stores/learning.ts')
      const { pinia } = await import('/src/stores/index.ts')
      return useLearningStore(pinia).taskPage.items.length
    }), 0)
    await page.screenshot({ path: path.join(output, 'account-b-empty.png'), fullPage: true })
    assert.deepEqual(errors, [])
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({
      races: findings, oldFinally: 'passed', old401: 'passed', fullNavigation: 'passed',
      accountBFailureIsolation: 'passed', rapidFilterUI: 'passed', pageErrors: errors,
    }, null, 2))
    console.log(JSON.stringify({ cr4_browser: 'passed', baseline_races_failed: 2,
      latest_races_passed: 2, old_finally: 'passed', account_switch: 'passed', old_401: 'passed' }))
  } finally {
    clearTimeout(deadline)
    await browser.close()
    if (fs.existsSync(baselinePath)) fs.unlinkSync(baselinePath)
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
