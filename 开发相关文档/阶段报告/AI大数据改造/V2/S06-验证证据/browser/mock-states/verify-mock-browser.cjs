const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { chromium } = require('playwright')
const root = process.cwd()
const v2 = path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2')
const evidence = path.join(v2, 'S06-验证证据/browser/mock-states')
assert.ok(!fs.existsSync(evidence), 'new evidence directory required; do not overwrite an earlier round')
fs.mkdirSync(evidence, { recursive: true })
const log = fs.openSync(path.join(evidence, 'frontend-server.log'), 'w')
const frontend = spawn('node', [path.join(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5177', '--strictPort'], {
  cwd: path.join(root, 'frontend'), env: { ...process.env, VITE_API_BASE_URL: 'http://127.0.0.1:8017/api/v1' }, stdio: ['ignore', log, log], windowsHide: true,
})
const payload = JSON.parse(fs.readFileSync(path.join(v2, 'S05-发布输入/v2-controlled/payload.json'), 'utf8'))
const firstId = '11111111-1111-4111-8111-111111111111'
const secondId = '22222222-2222-4222-8222-222222222222'
function mockDetail(id) {
  const { owner_user_id, source_counts, dataset_id, snapshot_id, job_id, ...detail } = structuredClone(payload)
  return { ...detail, batch_id: id, source: { dataset_id, snapshot_id, job_id }, published_at: '2026-10-21T05:00:00Z' }
}
const first = mockDetail(firstId)
const second = mockDetail(secondId)
let mode = 'normal'
let waitingDetail
const checks = [], errors = []
function check(name, condition) { assert.ok(condition, name); checks.push(name) }
const base = 'http://127.0.0.1:5177'
let browser
;(async () => {
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(base)).ok) break } catch {}
    if (attempt === 99) throw new Error('isolated mock frontend did not start')
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  await context.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 's06-mock-session-no-server-credential'))
  await context.route('http://127.0.0.1:8017/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const headers = { 'access-control-allow-origin': base, 'access-control-allow-headers': 'Authorization,Content-Type', 'access-control-allow-methods': 'GET,OPTIONS' }
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 200, headers, body: '' })
    const reply = body => route.fulfill({ status: 200, headers, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/api/v1/users/me') return reply({ id: 3, username: 's06_mock_student', email: 's06-mock@example.invalid' })
    if (url.pathname === '/api/v1/campus/me') return reply({ membership: null })
    if (url.pathname === '/api/v1/offline-analytics/batches') return reply({ items: [first, second], total: 2, page: 1, page_size: 20, empty_reason: null })
    if (url.pathname === '/api/v1/offline-analytics/batches/' + secondId && mode === 'delayed') {
      waitingDetail = route
      return
    }
    if (url.pathname.startsWith('/api/v1/offline-analytics/batches/')) {
      const item = structuredClone(url.pathname.endsWith(firstId) ? first : second)
      if (mode === 'unsupported') item.metric_version = 'unsupported-0.9'
      if (mode === 'unknown-duration' || mode === 'known-zero') {
        const unknown = mode === 'unknown-duration'
        Object.assign(item.records_summary, { known_minutes: 0, known_duration_count: unknown ? 0 : 4, missing_duration_count: unknown ? 4 : 0, known_zero_count: unknown ? 0 : 4 })
        item.daily.forEach(day => Object.assign(day, { known_minutes: 0, known_duration_count: unknown ? 0 : day.records, missing_duration_count: unknown ? day.records : 0, known_zero_count: unknown ? 0 : day.records }))
      }
      return reply(item)
    }
    throw new Error('unhandled mock request path')
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  const navigate = () => page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + firstId)
  mode = 'unsupported'
  await navigate()
  await page.getByRole('alert').waitFor()
  check('未知metric_version明确拒绝且无图表', (await page.getByRole('alert').innerText()).includes('口径暂不支持') && await page.locator('[data-chart-batch]').count() === 0)
  await page.screenshot({ path: path.join(evidence, 'unsupported-version.png'), fullPage: true })

  mode = 'unknown-duration'
  await navigate()
  await page.getByTestId('known-minutes').waitFor()
  check('全部分钟未知保留缺失而非填成真实零', (await page.locator('.offline-facts').innerText()).includes('缺失4条') && (await page.locator('.offline-daily tbody').innerText()).includes('时长未知'))
  await page.screenshot({ path: path.join(evidence, 'unknown-duration.png'), fullPage: true })
  mode = 'known-zero'
  await navigate()
  await page.getByTestId('known-minutes').waitFor()
  check('已知零与未知时长可区分', (await page.locator('.offline-facts').innerText()).includes('明确为零4条') && !(await page.locator('.offline-daily tbody').innerText()).includes('时长未知'))
  await page.screenshot({ path: path.join(evidence, 'known-zero.png'), fullPage: true })

  mode = 'normal'
  await navigate()
  await page.getByTestId('known-minutes').getByText('75', { exact: true }).waitFor()
  mode = 'delayed'
  await page.getByLabel('分析批次', { exact: true }).selectOption(secondId)
  await page.getByRole('status').waitFor()
  check('新批次响应前保留旧批次标题及完整图表', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === firstId && await page.locator('[data-chart-batch]').getAttribute('data-chart-batch') === firstId)
  await page.getByLabel('分析批次', { exact: true }).selectOption(firstId)
  await page.getByRole('status').waitFor({ state: 'detached' })
  check('重新选择旧批次先完成时身份一致', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === firstId)
  assert.ok(waitingDetail, 'held second detail request captured')
  await waitingDetail.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(second), headers: { 'access-control-allow-origin': base } }).catch(() => {})
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  check('晚到的旧请求不会覆盖最新选择', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === firstId && await page.locator('[data-chart-batch]').getAttribute('data-chart-batch') === firstId)
  await page.screenshot({ path: path.join(evidence, 'late-response-keeps-selection.png'), fullPage: true })
  check('Mock状态页面无脚本错误', errors.length === 0)
  fs.writeFileSync(path.join(evidence, 'verification.json'), JSON.stringify({ status: 'passed', mode: 'Mock API fulfillment only; no database, Spark or real model calls', checks, page_errors: errors }, null, 2))
  console.log(JSON.stringify({ status: 'passed', mode: 'mock-only', checks: checks.length }))
})().catch(error => { console.error(error.stack); process.exitCode = 1 }).finally(async () => {
  if (browser) await browser.close()
  frontend.kill()
  fs.closeSync(log)
})
