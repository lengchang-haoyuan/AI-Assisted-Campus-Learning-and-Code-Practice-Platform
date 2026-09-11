// P21 浏览器验收：API 均为虚构响应，真实数据库闭环由 verify_p21_governance.py 单独验证。
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:5173'
const evidenceDir = path.resolve(__dirname, '../../开发相关文档/测试证据')
const now = '2026-09-11T10:10:00Z'
const user = { id: 1, username: 'p21_admin_demo', email: 'p21@example.invalid', avatar_url: null, bio: null, is_active: true, created_at: now, updated_at: now }
const project = { id: 7, name: '校园 Python 练习库', description: '用于验证 P21 发布申请页面的虚构项目。', difficulty: 'beginner', language: 'Python', framework: 'FastAPI', frontend: 'Vue 3', backend: 'FastAPI', database: 'MySQL', requirements: [{ title: '基础练习' }], output_requirement: '提交可阅读的练习说明', status: 'in_progress', owner: { id: 1, username: user.username }, tags: [], is_published: false, published_at: null, view_count: 0, progress: 35, created_at: now, updated_at: now }
const publicProject = { id: 8, publication_id: 31, publication_kind: 'practice_template', publication_status: 'approved', publication_version: 2, name: 'Python 字符串基础练习', description: '从颠倒字符串开始的实践模板。', difficulty: 'beginner', status: 'in_progress', language: 'Python', framework: null, frontend: null, backend: null, database: null, repository_url: null, attribution: '张老师', source_license_statement: '教师原创教学材料', ai_assistance_statement: 'AI 仅用于语言润色，题目由教师复核', human_review_statement: '已逐题检查目标、难度和参考答案', owner: { id: 2, username: 'teacher_demo', avatar_url: null }, tags: [{ id: 1, name: 'Python', slug: 'python' }], published_at: now, updated_at: now, view_count: 5, comment_count: 1, like_count: 1, favorite_count: 1, liked: false, favorited: true }
const version = { version_number: 2, kind: 'practice_template', name: publicProject.name, description: publicProject.description, difficulty: 'beginner', project_status: 'in_progress', language: 'Python', framework: null, frontend: null, backend: null, database: null, repository_url: null, tags: ['Python'], attribution: publicProject.attribution, source_license_statement: publicProject.source_license_statement, ai_assistance_statement: publicProject.ai_assistance_statement, human_review_statement: publicProject.human_review_statement, submitted_at: now }
const pendingPublication = { id: 41, project_id: 7, owner_user_id: 4, kind: 'work', status: 'pending_review', public_version_number: null, pending_version_number: 1, revision: 1, submitted_at: now, reviewed_at: null, published_at: null, withdrawn_at: null, taken_down_at: null, public_version: null, pending_version: { ...version, version_number: 1, kind: 'work', name: '待审校园作品', attribution: 'student_demo', human_review_statement: null }, actions: [] }
const caseItem = { id: 51, case_type: 'report', opened_by_user_id: 6, target_owner_user_id: 2, target_type: 'project', publication_id: 31, publication_version_number: 2, comment_id: null, target_action_id: null, reason: '作品说明包含失效链接', target_excerpt: publicProject.name, status: 'pending', resolution_reason: null, resolved_action_id: null, revision: 1, created_at: now, resolved_at: null }
const pageOf = items => ({ items, total: items.length, page: 1, page_size: 20, total_pages: items.length ? 1 : 0 })

async function main() {
  fs.mkdirSync(evidenceDir, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'p21-fake-token'))
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const url = new URL(request.url()); const apiPath = url.pathname; const method = request.method()
    const respond = (data, status = 200) => route.fulfill({ status, json: data })
    if (apiPath.endsWith('/users/me')) return respond(user)
    if (apiPath.endsWith('/campus/me')) return respond({ membership: { id: 1, role: 'administrator', status: 'active', revision: 1, verified_at: now } })
    if (apiPath.endsWith('/community/projects') && method === 'GET') return respond({ items: [publicProject], total: 1, page: 1, page_size: 12, total_pages: 1 })
    if (apiPath.endsWith('/community/tags')) return respond([{ id: 1, name: 'Python', slug: 'python', project_count: 1 }])
    if (apiPath.endsWith('/community/projects/8')) return respond(publicProject)
    if (apiPath.endsWith('/projects/8/view')) return respond({ view_count: 6 })
    if (apiPath.endsWith('/projects/8/comments')) return respond({ items: [{ id: 61, project_id: 8, author: { id: 3, username: 'student_demo', avatar_url: null }, content: '题目层次清楚。', revision: 1, created_at: now, updated_at: now, can_delete: false, can_report: true }], total: 1, page: 1, page_size: 20, total_pages: 1 })
    if (apiPath.endsWith('/community/publications/mine')) return respond(pageOf([]))
    if (apiPath.endsWith('/community/moderation/publications')) return respond(pageOf([pendingPublication]))
    if (apiPath.endsWith('/community/governance/cases')) return respond(pageOf([caseItem]))
    if (apiPath.endsWith('/projects/7') && method === 'GET') return respond(project)
    if (apiPath.endsWith('/projects/7/publication')) return respond({ error: { code: 'not_found', message: '发布记录不存在', request_id: 'fake' } }, 404)
    errors.push(`未预期的 API 请求 ${method} ${apiPath}`)
    return respond({ error: { code: 'unexpected', message: 'Unexpected fake request', request_id: 'fake' } }, 500)
  })

  try {
    await page.goto(`${baseUrl}/community`)
    await page.getByRole('heading', { name: '校园代码社区' }).waitFor()
    await page.getByText('实践模板', { exact: true }).waitFor()
    assert.equal(await page.getByRole('link', { name: '治理进度' }).isVisible(), true)
    await page.screenshot({ path: path.join(evidenceDir, 'P21_校园社区_桌面.png'), fullPage: true })

    await page.goto(`${baseUrl}/community/projects/8`)
    await page.getByText('教师原创教学材料').waitFor()
    await page.getByText('AI 仅用于语言润色，题目由教师复核').waitFor()
    assert.equal(await page.getByRole('button', { name: '举报项目' }).isVisible(), true)
    assert.equal(await page.getByRole('button', { name: '举报', exact: true }).isVisible(), true)

    await page.goto(`${baseUrl}/community/governance`)
    await page.getByRole('heading', { name: '社区治理进度' }).waitFor()
    await page.getByRole('heading', { name: '待审发布申请' }).waitFor()
    await page.getByText('作品说明包含失效链接').waitFor()
    assert.equal(await page.getByRole('button', { name: '通过' }).isVisible(), true)
    assert.equal(await page.getByRole('button', { name: '支持并执行' }).isVisible(), true)
    await page.screenshot({ path: path.join(evidenceDir, 'P21_社区治理_管理员桌面.png'), fullPage: true })

    await page.goto(`${baseUrl}/projects/7`)
    await page.getByRole('button', { name: '申请发布' }).click()
    await page.getByRole('heading', { name: '校园社区发布申请' }).waitFor()
    assert.equal(await page.getByLabel('来源或许可说明').isVisible(), true)
    assert.equal(await page.getByLabel('AI 辅助使用声明').isVisible(), true)
    await page.setViewportSize({ width: 390, height: 844 })
    const root = page.locator('.project-detail-page')
    const overflow = await root.evaluate(element => element.scrollWidth - element.clientWidth)
    if (overflow > 1) {
      const offenders = await page.locator('.project-detail-page *').evaluateAll(elements => elements
        .map(element => ({ tag: element.tagName, className: element.className, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth }))
        .filter(item => item.scrollWidth - item.clientWidth > 1)
        .slice(0, 12))
      console.error({ overflow, offenders })
    }
    assert.ok(overflow <= 1, `窄屏内容不应横向溢出，实际 ${overflow}px`)
    await page.screenshot({ path: path.join(evidenceDir, 'P21_发布申请_窄屏.png'), fullPage: true })
    assert.deepEqual(errors, [])
    console.log('PASS: 社区模板声明、举报入口、管理员审核与案件处理、发布申请表、桌面与窄屏')
  } catch (error) {
    console.error({ url: page.url(), text: await page.locator('body').innerText(), errors })
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
