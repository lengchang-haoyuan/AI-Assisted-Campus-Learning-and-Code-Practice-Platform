// 沿用已有外部 Playwright；API 全部拦截为虚构数据，不访问数据库或模型。
const assert = require('node:assert/strict')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4181'
const now = '2026-09-28T04:00:00Z'
const emptyPage = { items: [], total: 0, page: 1, page_size: 100, total_pages: 0 }
const plans = ['draft', 'active', 'completed', 'cancelled'].map((status, index) => ({
  id: 11 + index, title: `${status}计划`, description: null, status,
  start_date: null, end_date: null, goal_data: null,
  progress: status === 'completed' ? 100 : 0, project: null, course: null,
  created_at: now, updated_at: now,
}))
let tasks = [
  [21, 13, 'completed'], [22, 14, 'pending'], [23, 12, 'pending'], [24, 99, 'completed'],
].map(([id, planId, status]) => ({
  id, title: `回归任务${id}`, description: null, priority: 'medium', status,
  scheduled_date: '2026-09-28', start_time: null, end_time: null, estimated_minutes: 30,
  completed_at: status === 'completed' ? now : null,
  plan: { id: planId, name: plans.find(plan => plan.id === planId)?.title || '分页外历史计划' },
  project: null, created_at: now, updated_at: now,
}))

async function main() {
  const browser = await chromium.launch({
    headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH,
  })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  const writes = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'learning-test-token'))
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const respond = data => route.fulfill({ status: 200, json: data })
    if (path.endsWith('/users/me')) return respond({
      id: 1, username: 'learning_test', email: 'learning@example.com',
      avatar_url: null, bio: null, is_active: true, created_at: now,
    })
    if (path.endsWith('/campus/me')) return respond({ membership: null })
    if (path.endsWith('/projects')) return respond(emptyPage)
    if (path.endsWith('/learning/plans')) return respond({
      ...emptyPage, items: plans, total: plans.length, total_pages: 1,
    })
    if (path.endsWith('/learning/tasks') && method === 'GET') return respond({
      ...emptyPage, items: tasks, total: tasks.length, total_pages: 1,
    })
    if (path.endsWith('/learning/tasks') && method === 'POST') {
      const input = request.postDataJSON()
      writes.push(input)
      const plan = plans.find(item => item.id === input.plan_id)
      const task = {
        ...input, id: 30, status: 'pending', completed_at: null,
        plan: plan ? { id: plan.id, name: plan.title } : null, project: null,
        created_at: now, updated_at: now,
      }
      tasks.push(task)
      return respond(task)
    }
    if (/\/learning\/tasks\/\d+$/.test(path) && method === 'PUT') {
      const id = Number(path.split('/').at(-1))
      const input = request.postDataJSON()
      writes.push(input)
      tasks = tasks.map(task => {
        if (task.id !== id) return task
        const plan = plans.find(item => item.id === input.plan_id)
        return {
          ...task, ...input,
          plan: plan ? { id: plan.id, name: plan.title } : input.plan_id ? task.plan : null,
        }
      })
      return respond(tasks.find(task => task.id === id))
    }
    errors.push(`未预期的 API 请求 ${method} ${path}`)
    return route.fulfill({ status: 500, json: { error: 'Unexpected test request' } })
  })

  const editor = page.locator('.learning-editor')
  const planSelect = editor.locator('label').filter({ hasText: '关联计划' }).locator('select')
  const titleInput = editor.getByPlaceholder('例如：完成课程项目数据库设计')
  async function openTask(id) {
    const task = tasks.find(item => item.id === id)
    const row = page.locator('.learning-task-board > li').filter({ hasText: task.title })
    await row.getByRole('button', { name: '编辑', exact: true }).click()
    await editor.waitFor()
  }
  async function saveTitle(title, expectedPlanId) {
    const before = writes.length
    await titleInput.fill(title)
    await editor.getByRole('button', { name: '保存任务', exact: true }).click()
    await editor.waitFor({ state: 'hidden' })
    assert.equal(writes.length, before + 1)
    assert.equal(writes.at(-1).plan_id, expectedPlanId)
  }
  try {
    await page.goto(`${baseUrl}/learning/tasks`)
    await page.locator('.learning-task-board').waitFor()
    await page.getByRole('button', { name: '创建任务', exact: true }).click()
    assert.deepEqual(await planSelect.locator('option').evaluateAll(options => options.map(option => option.value)), ['', '11', '12'])
    await titleInput.fill('合法草稿计划新任务')
    await planSelect.selectOption('11')
    await editor.getByRole('button', { name: '创建任务', exact: true }).click()
    await editor.waitFor({ state: 'hidden' })
    assert.equal(writes.at(-1).plan_id, 11)

    for (const [id, planId] of [[21, 13], [22, 14]]) {
      await openTask(id)
      assert.equal(await planSelect.isDisabled(), true)
      assert.equal(await planSelect.inputValue(), String(planId))
      assert.equal(await planSelect.locator(`option[value="${planId}"]`).count(), 1)
      const otherTerminalId = planId === 13 ? 14 : 13
      assert.equal(await planSelect.locator(`option[value="${otherTerminalId}"]`).count(), 0)
      await saveTitle(`历史标题已更新${id}`, planId)
    }

    await openTask(23)
    assert.equal(await planSelect.isDisabled(), false)
    await planSelect.selectOption('11')
    await saveTitle('活动任务合法改挂', 11)

    await openTask(24)
    assert.equal(await planSelect.inputValue(), '99')
    assert.equal(await planSelect.locator('option[value="99"]').count(), 1)
    await saveTitle('分页外历史标题已更新', 99)
    assert.deepEqual(errors, [])
    console.log('PASS: 新建仅选 draft/active、两种终态关联锁定和标题编辑、活动任务改挂、分页外当前关联保留；5 次虚构写入')
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
