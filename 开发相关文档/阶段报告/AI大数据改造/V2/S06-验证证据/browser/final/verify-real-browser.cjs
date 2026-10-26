const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')
const root = process.cwd()
const v2 = path.join(root, '开发相关文档/阶段报告/AI大数据改造/V2')
const evidence = process.env.S06_EVIDENCE
const round = process.env.S06_BROWSER_ROUND
const old = JSON.parse(fs.readFileSync(path.join(v2, 'S05-S06交接索引.json'), 'utf8'))
const freshPath = path.join(v2, 'S06-发布结果.json')
const fresh = round === 'final' ? JSON.parse(fs.readFileSync(freshPath, 'utf8')) : null
const main = fresh?.primary.batch_id || old.primary.batch_id
const boundary = fresh?.boundary.batch_id || old.boundary.batch_id
const expectedMinutes = fresh ? 90 : 75
const empty = '45c55b05-ff63-4cc6-b6ca-734146054710'
const base = 'http://127.0.0.1:5176'
const api = 'http://127.0.0.1:8016/api/v1'
const checks = [], responses = [], errors = []
function check(name, condition) { assert.ok(condition, name); checks.push(name) }
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))) })
}
async function shot(page, name) {
  await settle(page)
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: path.join(evidence, name), fullPage: true })
}
async function mainline() {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  try {
    async function contextFor(uid, width = 1440) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' })
      if (uid) await context.addInitScript(token => {
        // 只在首次载入种入隔离凭证，退出后不能由初始化脚本自动重新登录。
        if (!sessionStorage.getItem('s06.test-seeded')) {
          sessionStorage.setItem('scholarhub.access_token', token)
          sessionStorage.setItem('s06.test-seeded', '1')
        }
      }, process.env['S06_TEST_TOKEN' + uid])
      const page = await context.newPage()
      page.on('pageerror', error => errors.push(error.message))
      page.on('response', async response => {
        if (response.url().startsWith(api + '/offline-analytics')) {
          const body = await response.json().catch(() => null)
          responses.push({ url: response.url(), status: response.status(), body })
        }
      })
      return { context, page }
    }
    const { context, page } = await contextFor(3)
    await page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + main)
    await page.getByTestId('known-minutes').getByText(String(expectedMinutes), { exact: true }).waitFor()
    check('真实本人页面对应固定批次', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === main)
    check('分钟来自真实发布结果', await page.getByTestId('known-minutes').textContent() === String(expectedMinutes))
    check('任务分子分母精确50%', (await page.getByTestId('task-rate').textContent()) === '50.0%')
    check('确认与群组2比3', (await page.getByTestId('confirmation-count').textContent()) === '2 / 3')
    await page.locator('.offline-chart-grid canvas').first().waitFor()
    check('四类图表同屏同批', await page.locator('[data-chart-batch]').getAttribute('data-chart-batch') === main && await page.locator('.offline-figure canvas').count() === 4)
    check('规则与首次确认反例存在', await page.locator('[data-rule]').count() === 5 && (await page.locator('[data-rule="first_pass_counterexample"]').innerText()).includes('修订不是确认的必经步骤'))
    await shot(page, 'desktop.png')
    await page.locator('.offline-chart-grid').screenshot({ path: path.join(evidence, 'desktop-charts.png'), style: '.app-topbar, .studio-mobile-navigation { visibility: hidden !important; }' })
    await page.getByRole('button', { name: '记录数', exact: true }).click()
    check('记录覆盖视图可切换', await page.getByRole('button', { name: '记录数', exact: true }).getAttribute('aria-pressed') === 'true')
    await page.locator('.offline-figure').first().screenshot({ path: path.join(evidence, 'desktop-record-count.png'), style: '.app-topbar, .studio-mobile-navigation { visibility: hidden !important; }' })
    await page.getByRole('button', { name: '分钟', exact: true }).click()
    if (fresh) {
      const feedbackText = await page.locator('[data-rule="pending_review"]').innerText()
      check('首次反馈覆盖均值和冻结四区间可核对', feedbackText.includes('首次反馈覆盖2/3') && feedbackText.includes(fresh.primary.details.topic_summary.first_review_wait_mean_minutes + '分钟') && feedbackText.includes('少于60分钟2个') && feedbackText.includes('60至不足240分钟0个') && feedbackText.includes('240至不足1440分钟0个') && feedbackText.includes('1440分钟及以上0个'))
    }
    const requestCount = responses.length
    await page.locator('[data-rule="revision_observed"] summary').focus()
    await page.keyboard.press('Enter')
    check('规则可键盘展开', await page.locator('[data-rule="revision_observed"] details').getAttribute('open') !== null)
    check('切图和解释不触发分析请求', responses.length === requestCount)
    await page.getByRole('button', { name: '刷新批次', exact: true }).click()
    await page.getByRole('button', { name: '刷新批次', exact: true }).waitFor()
    check('刷新不替换用户正在看的历史', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === main)
    await page.setViewportSize({ width: 390, height: 844 })
    await settle(page)
    check('390px页面没有横向溢出', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    await shot(page, 'mobile.png')
    await page.locator('.offline-chart-grid').screenshot({ path: path.join(evidence, 'mobile-charts.png'), style: '.app-topbar, .studio-mobile-navigation { visibility: hidden !important; }' })
    await context.setOffline(true)
    await page.getByRole('button', { name: '刷新批次', exact: true }).click()
    await page.getByRole('alert').waitFor()
    check('真实断网保留旧完整批次', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === main && (await page.getByRole('alert').innerText()).includes('上一成功批次'))
    await shot(page, 'network-failure-keeps-batch.png')
    await context.setOffline(false)
    await page.getByRole('button', { name: '重试请求', exact: true }).click()
    await page.getByRole('alert').waitFor({ state: 'detached' })
    check('联网重试仍回到同一批次', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === main)
    await page.getByLabel('开始日期', { exact: true }).fill('2025-01-01')
    await page.getByLabel('结束日期', { exact: true }).fill('2025-01-02')
    await page.getByRole('button', { name: '筛选周期', exact: true }).click()
    await page.getByRole('heading', { name: '这个周期还没有分析', exact: true }).waitFor()
    check('日期筛选为空不混用旧图表', await page.locator('[data-chart-batch]').count() === 0)
    await page.getByLabel('数据来源', { exact: true }).selectOption('business')
    await page.getByRole('heading', { name: '从一次完整的分析开始', exact: true }).waitFor()
    check('首次无业务批次有明确空态', await page.locator('[data-batch-id]').count() === 0)
    await page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + empty)
    await page.getByRole('heading', { name: '本批没有可绘制样本', exact: true }).waitFor()
    check('真实空批次先鉴权再显示无样本', (await page.getByTestId('task-rate').textContent()) === '无样本')
    await shot(page, 'empty-owned-batch.png')
    await page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + boundary)
    await page.getByRole('alert').waitFor()
    check('本人不能查看他人批次且不遗留旧图', await page.locator('[data-batch-id]').count() === 0)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.getByRole('button', { name: '退出', exact: true }).click()
    await page.waitForURL(/\/login(?:\?|$)/)
    check('实际退出入口清空登录凭证与私人分析', await page.evaluate(() => sessionStorage.getItem('scholarhub.access_token')) === null && await page.locator('[data-batch-id]').count() === 0)
    await page.evaluate(token => sessionStorage.setItem('scholarhub.access_token', token), process.env.S06_TEST_TOKEN4)
    await page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + boundary)
    await page.getByTestId('task-rate').getByText('99.5%', { exact: true }).waitFor()
    check('同一浏览器换号后只展示新本人批次', await page.locator('[data-batch-id]').getAttribute('data-batch-id') === boundary && await page.getByTestId('known-minutes').textContent() === '0')
    await shot(page, 'same-browser-account-switch.png')
    await page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + main)
    await page.getByRole('alert').waitFor()
    check('换号后原本人批次被真实API拒绝且无旧内容', await page.locator('[data-batch-id]').count() === 0)
    const other = await contextFor(4)
    await other.page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + boundary)
    await other.page.getByTestId('task-rate').getByText('99.5%', { exact: true }).waitFor()
    check('另一本人199比200不四舍五入成全完成', (await other.page.getByTestId('task-rate').textContent()) === '99.5%')
    await shot(other.page, 'boundary-199-of-200.png')
    await other.page.goto(base + '/offline-analytics?dataset_kind=controlled&batch_id=' + empty)
    await other.page.getByRole('alert').waitFor()
    check('空批次他人仍被真实API拒绝', await other.page.locator('[data-batch-id]').count() === 0)
    const unauthenticated = await browser.newContext()
    const response = await unauthenticated.request.get(api + '/offline-analytics/batches/' + empty)
    check('空批次未登录真实401', response.status() === 401)
    check('页面脚本无错误', errors.length === 0)
    fs.writeFileSync(path.join(evidence, 'verification.json'), JSON.stringify({ status: 'passed', mode: 'real TCP API + authenticated MySQL, no API response fulfillment', batch_id: main, expected_minutes: expectedMinutes, checks, page_errors: errors, responses, viewport_widths: [1440, 390], writes_or_models_not_triggered_by_UI: 'verified separately by server-observation.json' }, null, 2))
    console.log(JSON.stringify({ status: 'passed', checks: checks.length, actual_api_responses: responses.length, batch_id: main }))
  } finally { await browser.close() }
}
mainline().catch(error => { console.error(error.stack); process.exitCode = 1 })
