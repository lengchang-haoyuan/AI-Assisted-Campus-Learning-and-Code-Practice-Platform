// 视觉改版验收：所有 API 在浏览器中拦截，不访问业务数据库或真实模型。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:5173'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseUrl).hostname), '只允许本地前端验收')
const output = process.env.SCHOLARHUB_STUDIO_EVIDENCE || path.resolve(__dirname, '../../开发相关文档/测试证据/20261014-Campus-Studio')
const now = '2026-10-14T03:00:00Z'
const pageData = items => ({ items, total: items.length, page: 1, page_size: 100, total_pages: items.length ? 1 : 0 })
const fields = { description: null, difficulty: 'beginner', framework: null, frontend: null, backend: null, database: null, requirements: null, output_requirement: null, is_published: false, published_at: null, view_count: 0, owner: { id: 1, username: 'studio_student' }, tags: [], created_at: now, updated_at: now }
const seedProjects = [
  { id: 1, name: '校园失物招领平台', language: 'TypeScript', frontend: 'Vue 3', backend: 'FastAPI', description: '把校园里的小问题，变成可以运行的作品。', status: 'in_progress', progress: 62 },
  { id: 2, name: '图书管理系统', language: 'Java', database: 'MySQL', description: '从借阅流程开始，练习完整的业务闭环。', status: 'in_progress', progress: 35 },
  { id: 3, name: 'Vue组件实验室', language: 'TypeScript', framework: 'Vue 3', description: '拆解交互细节，构建可复用的小组件。', status: 'not_started', progress: 0 },
  { id: 4, name: 'Python数据练习', language: 'Python', description: '从清洗与整理开始，理解数据处理过程。', status: 'in_progress', progress: 40 },
  { id: 5, name: 'Java基础实践', language: 'Java', description: '通过小项目巩固输入、判断与循环。', status: 'completed', progress: 100 },
  { id: 6, name: '个人学习笔记', language: 'TypeScript', framework: 'Vue 3', database: 'MySQL', description: '记录每天的学习过程与实践心得。', status: 'not_started', progress: 0 },
].map(project => ({ ...fields, ...project }))
const courses = ['Web前端开发', 'Python程序设计', 'Java程序设计'].map((name, index) => ({ id: index + 1, name, code: `COURSE-${index + 1}`, instructor: null, description: null, schedule_data: null, status: 'active', created_at: now, updated_at: now }))
const plans = [
  { id: 11, title: 'Vue组件实践计划', description: '拆解交互细节，完成一组可复用的界面组件。', status: 'active', progress: 60, project: { id: 3, name: seedProjects[2].name }, course: { id: 1, name: courses[0].name } },
  { id: 12, title: 'Python数据处理入门', description: '练习数据读取、清洗与整理，建立处理思路。', status: 'active', progress: 40, project: { id: 4, name: seedProjects[3].name }, course: { id: 2, name: courses[1].name } },
  { id: 13, title: 'Java基础巩固', description: '通过小项目练习输入、判断、循环与数据处理。', status: 'completed', progress: 100, project: { id: 5, name: seedProjects[4].name }, course: { id: 3, name: courses[2].name } },
].map(plan => ({ start_date: '2026-10-01', end_date: '2026-10-31', goal_data: null, created_at: now, updated_at: now, ...plan }))
const report = { id: 1, period_start: '2026-10-08', period_end: '2026-10-14', status: 'completed', summary: '本周完成了项目与课程练习，建议继续保持规律学习，并整理实践中的问题。', achievement: ['完成基础实践任务'], problems: ['补齐学习记录'], suggestions: ['继续组件与数据练习'], structured_data: { total_learning_minutes: 180, active_days: 4, task_completion_rate: 75, project_average_progress: 70, workflow_success_rate: 100, ai_request_count: 0, performance_level: 'steady', focus_areas: ['项目实践'], recommended_weekly_minutes: 180 }, error: null, generated_at: now, created_at: now, updated_at: now }

async function main() {
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  const context = await browser.newContext({ viewport: { width: 1487, height: 1058 }, timezoneId: 'Asia/Shanghai' })
  await context.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'studio-isolated-test-token'))
  const page = await context.newPage()
  await page.clock.setFixedTime(new Date(now))
  const errors = []
  const writes = []
  const requests = []
  let mode = 'normal'
  let role = 'student'
  let projects = structuredClone(seedProjects)
  page.on('pageerror', error => errors.push(error.message))
  await context.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const endpoint = url.pathname.replace('/api/v1', '')
    const method = request.method()
    requests.push({ method, endpoint, query: url.search })
    const respond = json => route.fulfill({ status: 200, json })
    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': baseUrl, 'access-control-allow-headers': 'authorization,content-type', 'access-control-allow-methods': 'GET,POST,PUT,DELETE' } })
    if (endpoint === '/users/me') return respond({ id: 1, username: 'studio_student', email: 'studio@example.test', is_active: true, created_at: now, updated_at: now })
    if (endpoint === '/campus/me') return respond({ campus: null, membership: role ? { id: 1, campus_id: 1, role, status: 'active', user_id: 1 } : null })
    if (endpoint === '/projects' && method === 'GET') {
      if (mode === 'error') return route.fulfill({ status: 503, json: { error: { message: '隔离测试的加载失败' } } })
      if (mode === 'empty') return respond(pageData([]))
      const selected = Number(url.searchParams.get('page') || '1')
      return respond({ ...pageData(projects), items: selected === 1 ? projects : [projects[0]], total: 18, page: selected, page_size: 12, total_pages: 2 })
    }
    const projectMatch = endpoint.match(/^\/projects\/(\d+)$/)
    if (projectMatch) {
      const id = Number(projectMatch[1])
      const project = projects.find(item => item.id === id)
      if (method === 'PUT') { const input = request.postDataJSON(); writes.push({ method, endpoint, input }); Object.assign(project, input); return respond(project) }
      if (method === 'DELETE') { writes.push({ method, endpoint }); projects = projects.filter(item => item.id !== id); return route.fulfill({ status: 204 }) }
      return respond(project)
    }
    if (/^\/projects\/\d+\/publication$/.test(endpoint)) return route.fulfill({ status: 404, json: { detail: 'No publication in isolated fixture' } })
    if (endpoint === '/courses') return respond(pageData(courses))
    if (endpoint === '/learning/plans') return respond(pageData(plans))
    if (endpoint === '/statistics/today') return respond({ date: '2026-10-14', timezone_offset_minutes: 480, visitors: 18, completed_task_users: 3, project_total: 12, published_project_total: 2, projects_created: 2, projects_published: 1, community_interactions: 26 })
    if (endpoint === '/statistics/trend') {
      const days = Number(url.searchParams.get('days'))
      return respond({ days, start_date: '2026-10-08', end_date: '2026-10-14', timezone_offset_minutes: 480, items: Array.from({ length: 7 }, (_, i) => ({ date: `2026-10-${String(8 + i).padStart(2, '0')}`, visitors: [8, 10, 7, 11, 14, 12, 18][i], completed_task_users: [1, 2, 1, 2, 3, 2, 3][i], completed_tasks: [1, 2, 1, 2, 3, 2, 3][i], community_interactions: [10, 14, 9, 15, 19, 17, 26][i], projects_created: [1, 2, 0, 1, 1, 1, 2][i], projects_completed: [0, 1, 1, 0, 1, 1, 1][i], projects_published: [0, 0, 0, 0, 0, 1, 1][i] })) })
    }
    if (endpoint === '/statistics/projects') return respond({ days: Number(url.searchParams.get('days')), total: 12, published: 2, completed: 5, average_progress: 70, statuses: [{ status: 'not_started', count: 2 }, { status: 'in_progress', count: 3 }, { status: 'completed', count: 5 }, { status: 'published', count: 2 }, { status: 'archived', count: 0 }], completion_trend: [] })
    if (endpoint === '/statistics/tech-stacks') return respond({ total_projects: 12, dimensions: ['language', 'framework', 'frontend', 'backend', 'database'].map((key, index) => ({ key, label: ['语言', '框架', '前端', '后端', '数据库'][index], items: (key === 'language' ? ['Java', 'Python', 'TypeScript'] : ['Vue 3', 'FastAPI', 'MySQL']).map((name, i) => ({ name, count: [6, 4, 2][i], percentage: [50, 33.33, 16.67][i] })) })) })
    if (endpoint === '/learning-reports') {
      if (method === 'POST') { writes.push({ method, endpoint, input: request.postDataJSON() }); return respond(report) }
      return respond(pageData([report]))
    }
    errors.push(`Unexpected fixture request ${method} ${endpoint}`)
    return route.fulfill({ status: 500, json: { detail: 'Unexpected isolated fixture endpoint' } })
  })
  const settle = async () => {
    await page.locator('.campus-studio').waitFor()
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(650)
  }
  const capture = async (routePath, filename, viewport, fullPage = false) => {
    await page.setViewportSize(viewport)
    await page.goto(`${baseUrl}${routePath}`)
    await settle()
    await page.screenshot({ path: path.join(output, filename), fullPage })
  }
  const checks = []
  try {
    // 新会话先验证低像素密度手机确实选择小图，避免桌面缓存影响选图。
    await capture('/', 'mobile-source.png', { width: 390, height: 844 })
    await page.locator('.studio-featured-cover').evaluate(image => image.decode())
    const responsiveImage = await page.locator('.studio-featured-cover').evaluate(image => image.currentSrc)
    assert.match(responsiveImage, /noticeboard-400\.webp/)
    checks.push('mobile responsive WebP source')
    // 一批桌面/手机截图，同时覆盖目标四页。
    await capture('/', 'desktop-home.png', { width: 1487, height: 1058 })
    await capture('/projects', 'desktop-projects.png', { width: 1487, height: 1058 })
    await capture('/learning', 'desktop-learning.png', { width: 1487, height: 1058 })
    await capture('/analytics', 'desktop-analytics.png', { width: 1487, height: 1058 }, true)
    await capture('/', 'mobile-home.png', { width: 390, height: 844 })
    checks.push('desktop/mobile screenshots')

    await page.getByRole('button', { name: '开始专注', exact: true }).click()
    await page.waitForTimeout(1200)
    assert.notEqual(await page.locator('.focus-time').innerText(), '25:00')
    await page.getByRole('button', { name: '暂停专注', exact: true }).click()
    await page.getByRole('button', { name: '重置', exact: true }).click()
    assert.equal(await page.locator('.focus-time').innerText(), '25:00')
    checks.push('focus start/pause/reset')

    await page.getByRole('button', { name: '更多', exact: true }).click()
    assert.ok(await page.getByRole('dialog', { name: '全部功能' }).isVisible())
    assert.ok(await page.getByRole('dialog').getByRole('link', { name: '成果', exact: true }).isVisible())
    assert.equal(await page.getByRole('dialog').getByRole('link', { name: '校园管理', exact: true }).count(), 0)
    await page.getByRole('dialog').getByRole('link', { name: '首页', exact: true }).click()
    await page.getByRole('dialog').waitFor({ state: 'hidden' })
    assert.equal(await page.getByRole('dialog').isVisible(), false)
    await page.getByRole('button', { name: '更多', exact: true }).click()
    await page.keyboard.press('Escape')
    assert.equal(await page.getByRole('dialog').isVisible(), false)
    assert.match(await page.evaluate(() => document.activeElement.textContent), /更多/)
    checks.push('mobile navigation and keyboard dismissal')

    await page.getByRole('button', { name: '打开项目搜索' }).click()
    await page.getByLabel('搜索项目或技术栈', { exact: true }).fill('Vue')
    await page.locator('.global-search').getByRole('button', { name: '搜索', exact: true }).click()
    await page.waitForURL('**/projects?q=Vue')
    await page.locator('.search-result-bar').waitFor()
    await page.locator('.project-flip-card').first().waitFor()
    assert.ok(await page.locator('.project-flip-card').count() >= 2)
    checks.push('global project search keeps q contract')

    await page.setViewportSize({ width: 1487, height: 1058 })
    await page.goto(`${baseUrl}/projects`)
    await settle()
    await page.getByRole('button', { name: '新建项目', exact: true }).click()
    await page.getByRole('heading', { name: '创建项目', exact: true }).waitFor()
    await page.locator('.project-form').getByRole('button', { name: '取消', exact: true }).click()
    const flipTrigger = page.getByRole('button', { name: '查看技术详情', exact: true }).first()
    await flipTrigger.focus()
    await page.keyboard.press('Enter')
    const openProject = page.getByRole('link', { name: '打开项目', exact: true }).first()
    await openProject.waitFor()
    assert.ok(await openProject.evaluate(link => link === document.activeElement))
    await page.getByRole('button', { name: '返回封面', exact: true }).first().focus()
    await page.keyboard.press('Enter')
    await flipTrigger.waitFor()
    assert.ok(await flipTrigger.evaluate(button => button === document.activeElement))
    await page.keyboard.press('Enter')
    await openProject.waitFor()
    checks.push('keyboard card flip focus restoration')
    await page.locator('.project-flip-card__back').first().getByRole('button', { name: '编辑', exact: true }).click()
    await page.waitForURL('**/projects/1?edit=1')
    await page.getByLabel('项目名称', { exact: true }).fill('校园失物招领平台·验收')
    await page.locator('.project-form').getByRole('button', { name: '保存修改', exact: true }).click()
    await page.getByText('项目已更新；已公开内容仍使用审核通过的快照', { exact: true }).waitFor()
    assert.equal(writes.find(write => write.method === 'PUT')?.input.name, '校园失物招领平台·验收')
    assert.deepEqual(Object.keys(writes.find(write => write.method === 'PUT').input).sort(), ['name', 'description', 'difficulty', 'language', 'framework', 'frontend', 'backend', 'database', 'requirements', 'output_requirement', 'status'].sort())
    checks.push('create form, flip, edit and unchanged PUT fields')

    await page.goto(`${baseUrl}/projects`)
    await settle()
    await page.getByRole('button', { name: '下一页', exact: true }).click()
    await page.getByText('第 2 / 2 页', { exact: true }).waitFor()
    assert.ok(requests.some(request => request.endpoint === '/projects' && request.query.includes('page=2')))
    checks.push('existing project pagination')

    await page.goto(`${baseUrl}/learning`)
    await settle()
    await page.getByRole('tab', { name: '课程档案', exact: true }).click()
    assert.equal(await page.locator('.learning-course-list article').count(), 3)
    await page.getByRole('tab', { name: '学习计划', exact: true }).click()
    assert.equal(await page.locator('.learning-plan-card').count(), 3)
    await page.locator('.learning-plan-card').first().getByRole('button', { name: '编辑', exact: true }).click()
    await page.getByRole('heading', { name: '编辑计划', exact: true }).waitFor()
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    checks.push('learning views and plan editor')

    await page.goto(`${baseUrl}/analytics`)
    await settle()
    await page.getByRole('tab', { name: '近 30 日', exact: true }).click()
    await page.waitForTimeout(100)
    assert.ok(requests.some(request => request.endpoint === '/statistics/trend' && request.query.includes('days=30')))
    await page.getByRole('tab', { name: '数据库', exact: true }).click()
    await page.getByRole('button', { name: '生成报告', exact: true }).click()
    await page.getByText('学习报告已生成并保存', { exact: true }).waitFor()
    assert.deepEqual(writes.find(write => write.endpoint === '/learning-reports').input, { period_start: '2026-10-08', period_end: '2026-10-14', timezone_offset_minutes: 480 })
    checks.push('analytics range, dimensions and unchanged report POST')

    for (const width of [1487, 1040, 820, 760, 390, 320]) {
      for (const routePath of ['/', '/projects', '/learning', '/analytics']) {
        await page.setViewportSize({ width, height: 1058 })
        await page.goto(`${baseUrl}${routePath}`)
        await settle()
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${routePath} overflows at ${width}px`)
      }
    }
    checks.push('4 routes at 6 viewport widths')

    for (const variant of ['empty', 'error']) {
      mode = variant
      await page.goto(baseUrl)
      await settle()
      if (variant === 'empty') await page.getByRole('heading', { name: '从第一个项目开始' }).waitFor()
      else { await page.getByRole('alert').waitFor(); assert.ok(await page.getByRole('button', { name: '重试', exact: true }).isVisible()) }
      await page.screenshot({ path: path.join(output, `home-${variant}.png`), fullPage: true })
    }
    mode = 'normal'
    role = 'administrator'
    await page.goto(baseUrl)
    await settle()
    await page.getByRole('button', { name: '更多', exact: true }).click()
    assert.ok(await page.getByRole('dialog').getByRole('link', { name: '校园管理', exact: true }).isVisible())
    assert.equal(await page.getByRole('dialog').getByRole('link', { name: '成果', exact: true }).count(), 0)
    await page.getByRole('button', { name: '关闭导航' }).click()
    role = null
    await page.goto(baseUrl)
    await settle()
    await page.getByRole('button', { name: '更多', exact: true }).click()
    assert.equal(await page.getByRole('dialog').getByRole('link', { name: '教学班', exact: true }).count(), 0)
    checks.push('empty/error and unchanged campus role visibility')
    await page.getByRole('button', { name: '关闭导航' }).click()
    for (const membershipRole of [null, 'student', 'administrator']) {
      role = membershipRole
      for (const width of [1041, 1200, 1280]) {
        await page.setViewportSize({ width, height: 1058 })
        await page.goto(baseUrl)
        await settle()
        assert.ok(await page.getByRole('button', { name: '退出', exact: true }).isVisible(), `logout unavailable: ${membershipRole} at ${width}px`)
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
      }
    }
    checks.push('desktop logout for all roles at 1041/1200/1280px')
    assert.deepEqual(errors, [])
    const result = { result: 'passed', checks, responsive_image_source: responsiveImage, API_requests_intercepted: requests.length, database_writes: 0, model_calls: 0, viewport_widths: [1487, 1040, 820, 760, 390, 320], logout_viewport_widths: [1041, 1200, 1280] }
    fs.writeFileSync(path.join(output, 'verification.json'), JSON.stringify(result, null, 2))
    console.log(JSON.stringify(result))
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
    console.error(JSON.stringify({ url: page.url(), checks, errors, message: error.message }))
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
