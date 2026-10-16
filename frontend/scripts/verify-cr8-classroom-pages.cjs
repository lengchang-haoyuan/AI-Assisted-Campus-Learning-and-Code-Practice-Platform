const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { chromium } = require('playwright')
const base = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4181'
const output = path.resolve(__dirname, '../../开发相关文档/测试证据/CR8')
const beforeFile = path.resolve(__dirname, '../src/views/.CR8Before.vue')
const harnessFile = path.resolve(__dirname, '../src/.cr8-baseline.ts')
const now = '2026-10-16T04:00:00Z'
const empty = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const assignment = id => ({ id, class_id: 1, title: `教学任务${id}`, instructions: '完成教学任务并提交验证证据。',
  learning_objectives: ['理解输入'], acceptance_criteria: ['提交证据'], due_at: '2026-10-20T12:00:00Z',
  status: id === 21 ? 'draft' : id === 1 ? 'archived' : 'published', revision: 1,
  created_at: now, updated_at: now, source_project_snapshot: null, published_at: null,
  closed_at: null, archived_at: null, can_edit: true, can_publish: id === 21, can_close: false, can_archive: false })
const member = id => ({ id, campus_membership_id: 100 + id, user_id: id, username: `成员${id}`,
  member_role: 'student', status: id === 1 ? 'left' : 'active', joined_at: now, left_at: null, revision: 1 })
const paginate = (count, size, page, create) => ({ items: Array.from({ length: Math.max(0, Math.min(size, count - (page - 1) * size)) },
  (_, index) => create((page - 1) * size + index + 1)), total: count, page, page_size: size, total_pages: Math.ceil(count / size) })

async function main() {
  fs.mkdirSync(output, { recursive: true })
  assert(!fs.existsSync(beforeFile), '临时基线组件已存在')
  assert(!fs.existsSync(harnessFile), '临时基线入口已存在')
  // 固定修复前版本，提交后仍可复现原有分页缺口。
  fs.writeFileSync(beforeFile, execFileSync('git', ['show', '3d459ad:frontend/src/views/ClassroomDetailView.vue'],
    { cwd: path.resolve(__dirname, '../..'), encoding: 'utf8' }))
  fs.writeFileSync(harnessFile, `import { createApp } from 'vue'
import router from '@/router'
import { pinia } from '@/stores'
import Before from '@/views/.CR8Before.vue'
export function mountBaseline() {
  document.querySelector('#app')?.remove()
  const root = document.createElement('div'); document.body.append(root)
  createApp(Before).use(pinia).use(router).mount(root)
}`)
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SCHOLARHUB_BROWSER_PATH })
  try {
    const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'classroom-mock'))
    let taskCount = 21, memberCount = 51, role = 'teacher', failTasks = false, published = false
    let holdTasks = false
    const queue = []
    const nextTask = () => { const gate = deferred(); queue.push(gate); return gate.promise }
    await page.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url())
      const endpoint = url.pathname.replace('/api/v1', '')
      const pageNumber = Number(url.searchParams.get('page') || 1)
      const respond = json => route.fulfill({ status: 200, json })
      if (endpoint === '/users/me') return respond({ id: 1, username: 'fixture', email: 'fixture@example.invalid',
        is_active: true, avatar_url: null, bio: null, created_at: now })
      if (endpoint === '/campus/me') return respond({ membership: { id: 101, role, status: 'active', revision: 1, verified_at: now } })
      if (endpoint === '/campus/classes/1') return respond({ id: 1, name: '分页验收课堂', course_title: '项目实践', term_label: '2026秋',
        status: 'active', revision: 1, created_at: now, updated_at: now, archived_at: null, viewer_role: role,
        viewer_member_id: 1, viewer_member_revision: 1, can_edit: role === 'teacher', can_view_members: role === 'teacher',
        can_manage_members: role === 'teacher', can_create_assignments: role === 'teacher' })
      if (endpoint === '/campus/classes/1/assignments') {
        if (failTasks) { failTasks = false; return route.fulfill({ status: 500, json: {} }) }
        if (holdTasks) {
          const gate = deferred(); assert(queue.length); queue.shift().resolve(gate)
          await gate.promise
        }
        return respond(paginate(taskCount, 20, pageNumber, assignment))
      }
      if (endpoint === '/campus/classes/1/members') return respond(paginate(memberCount, 50, pageNumber, member))
      if (endpoint === '/campus/classes/1/members/51') { memberCount = 50; return respond({ ...member(51), status: 'removed', revision: 2 }) }
      if (endpoint === '/campus/assignments/21') return respond({ ...assignment(21), status: published ? 'published' : 'draft', can_publish: !published })
      if (endpoint === '/campus/assignments/21/publish') { published = true; return respond({ ...assignment(21), status: 'published', can_publish: false }) }
      return respond(empty)
    })
    await page.goto(`${base}/campus/classes/1`)
    await page.getByRole('heading', { name: '分页验收课堂', exact: true }).waitFor()
    const baselineRender = await page.evaluate(async () => {
      const { mountBaseline } = await import('/src/.cr8-baseline.ts')
      mountBaseline()
      return true
    })
    assert(baselineRender)
    await page.locator('.teaching-assignment-list > a').first().waitFor()
    assert.equal(await page.locator('.teaching-assignment-list > a').count(), 20)
    assert.equal(await page.locator('.teaching-member-list > article').count(), 50)
    assert.equal(await page.getByRole('navigation', { name: '教学任务分页' }).count(), 0)
    assert.equal(await page.getByRole('navigation', { name: '班级成员分页' }).count(), 0)
    console.log('CR8 baseline reproduced')
    const boundaries = []
    for (const [tasks, members] of [[0, 0], [1, 1], [20, 50], [21, 51]]) {
      taskCount = tasks; memberCount = members
      await page.goto(`${base}/campus/classes/1`)
      await page.getByRole('heading', { name: '分页验收课堂', exact: true }).waitFor()
      if (tasks) await page.locator('.teaching-assignment-list > a').first().waitFor()
      else await page.getByText('还没有教学任务。', { exact: true }).waitFor()
      assert.equal(await page.locator('.teaching-assignment-list > a').count(), Math.min(tasks, 20))
      assert.equal(await page.locator('.teaching-member-list > article').count(), Math.min(members, 50))
      boundaries.push({ tasks, members, passed: true })
    }
    console.log('CR8 boundaries passed')
    const taskNav = page.getByRole('navigation', { name: '教学任务分页' })
    const memberNav = page.getByRole('navigation', { name: '班级成员分页' })
    failTasks = true
    await taskNav.getByRole('button', { name: '下一页' }).click()
    const taskPanel = page.locator('.teaching-panel').filter({ has: page.getByRole('heading', { name: '任务列表', exact: true }) })
    await taskPanel.getByRole('alert').waitFor()
    await taskPanel.getByRole('button', { name: '重试', exact: true }).click()
    await page.getByRole('heading', { name: '教学任务21', exact: true }).waitFor()
    await taskNav.getByRole('button', { name: '上一页' }).click()
    await page.getByRole('heading', { name: '教学任务1', exact: true }).waitFor()
    await taskNav.getByRole('button', { name: '下一页' }).click()
    await page.getByRole('heading', { name: '教学任务21', exact: true }).waitFor()
    await memberNav.getByRole('button', { name: '下一页' }).click()
    await page.getByText('成员51', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(output, 'second-pages.png'), fullPage: true })
    await page.getByRole('link').filter({ has: page.getByRole('heading', { name: '教学任务21', exact: true }) }).click()
    await page.getByRole('button', { name: '发布任务', exact: true }).click()
    await page.locator('.el-message-box').getByRole('button', { name: /^(确定|OK|Confirm)$/ }).click()
    await page.getByText('任务已发布', { exact: true }).waitFor()
    assert(published)
    await page.goto(`${base}/campus/classes/1`)
    await memberNav.getByRole('button', { name: '下一页' }).click()
    await page.getByText('成员51', { exact: true }).waitFor()
    await page.locator('.teaching-member-list > article').getByRole('button', { name: '移除', exact: true }).click()
    await page.locator('.el-message-box').getByRole('button', { name: /^(确定|OK|Confirm)$/ }).click()
    await page.getByText('成员2', { exact: true }).waitFor()
    assert.equal(await memberNav.count(), 0)
    holdTasks = true
    const old = nextTask()
    await taskNav.getByRole('button', { name: '下一页' }).click()
    const oldGate = await old
    const latest = nextTask()
    await taskNav.getByRole('button', { name: '上一页' }).click()
    const latestGate = await latest
    latestGate.resolve()
    await page.getByRole('heading', { name: '教学任务1', exact: true }).waitFor()
    const oldResponse = page.waitForResponse(response => response.url().includes('/assignments?page=2'))
    oldGate.resolve(); await oldResponse
    assert.equal(await page.getByRole('heading', { name: '教学任务21', exact: true }).count(), 0)
    holdTasks = false
    memberCount = 51
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${base}/campus/classes/1`)
    await taskNav.getByRole('button', { name: '下一页' }).click()
    await memberNav.getByRole('button', { name: '下一页' }).click()
    await page.getByText('成员51', { exact: true }).waitFor()
    await page.getByRole('heading', { name: '教学任务21', exact: true }).waitFor()
    await taskNav.getByRole('button', { name: '上一页' }).click()
    await page.getByRole('heading', { name: '教学任务1', exact: true }).waitFor()
    await taskNav.getByRole('button', { name: '下一页' }).click()
    await page.getByRole('heading', { name: '教学任务21', exact: true }).waitFor()
    await taskNav.evaluate(element => element.scrollIntoView({ block: 'center' }))
    await page.screenshot({ path: path.join(output, 'teacher-mobile.png'), fullPage: false })
    role = 'student'; taskCount = 20
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${base}/campus/classes/1`)
    await page.getByRole('heading', { name: '已发布任务', exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: '加入班级', exact: true }).count(), 0)
    assert.equal(await page.getByRole('button', { name: '移除', exact: true }).count(), 0)
    await page.screenshot({ path: path.join(output, 'student-mobile.png'), fullPage: false })
    assert.deepEqual(errors, [])
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ boundaries,
      baselineHiddenSecondPages: true, draftPublish: published, memberRemovalFallback: true,
      retry: true, latestPageWins: true, studentPermissions: true, pageErrors: errors }, null, 2))
    console.log(JSON.stringify({ cr8_browser: 'passed', boundaries: 4, draft_publish: 'passed',
      member_fallback: 'passed', retry: 'passed', latest_page: 'passed', student_mobile: 'passed' }))
  } finally { await browser.close(); fs.unlinkSync(beforeFile); fs.unlinkSync(harnessFile) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
