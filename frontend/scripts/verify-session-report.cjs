// 使用外部已安装的 Playwright 和浏览器；不修改项目依赖或测试配置。
const assert = require('node:assert/strict')
const { randomBytes } = require('node:crypto')
const { execFileSync } = require('node:child_process')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const backend = path.resolve(__dirname, '../../backend')
const evidence = path.resolve(__dirname, '../../开发相关文档/测试证据/P15')
const frontendUrl = 'http://127.0.0.1:5173'
const apiUrl = 'http://127.0.0.1:8000/api/v1'
const tokenKey = 'scholarhub.access_token'
const users = []
const cleanupCode = `
import json
import sys
from sqlalchemy import delete, func, select
from app.models.user import User
from app.core.database import get_session_factory

pairs = json.loads(sys.argv[1])
with get_session_factory()() as session:
    for pair in pairs:
        session.execute(delete(User).where(
            User.id == pair["id"], User.username == pair["username"],
        ))
    session.commit()
    remaining = session.scalar(select(func.count(User.id)).where(
        User.username.in_([pair["username"] for pair in pairs]),
    ))
    if remaining:
        raise RuntimeError("浏览器回归临时账号清理失败")
print("浏览器回归临时账号已清理")
`

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.SCHOLARHUB_BROWSER_PATH,
  })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let phase = '注册临时用户'
  try {
    const suffix = randomBytes(5).toString('hex')
    for (const index of [1, 2]) {
      const username = `p15_session_${suffix}_${index}`
      const password = randomBytes(24).toString('base64url')
      const response = await context.request.post(`${apiUrl}/auth/register`, {
        data: { username, password, email: `${username}@example.invalid` },
      })
      assert.equal(response.status(), 201)
      users.push({ id: (await response.json()).id, username, password })
    }
    async function login(user) {
      await page.getByLabel('用户名或邮箱').fill(user.username)
      await page.getByLabel('密码', { exact: true }).fill(user.password)
      await page.getByRole('button', { name: '登录', exact: true }).click()
      await page.waitForURL(url => url.pathname === '/')
    }

    phase = '6 秒报告与重复提交'
    let savedReport = null
    let postCount = 0
    let failList = false
    await page.route('**/api/v1/learning-reports**', async route => {
      if (route.request().method() === 'POST') {
        postCount++
        const input = route.request().postDataJSON()
        await new Promise(resolve => setTimeout(resolve, 6000))
        savedReport = {
          id: 1, period_start: input.period_start, period_end: input.period_end,
          status: 'completed', summary: 'P15 明确标注的前端回归样本，不是真实模型结果',
          achievement: [], problems: [], suggestions: [], structured_data: null,
          error: null, generated_at: new Date().toISOString(),
          created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        }
        await route.fulfill({ status: 201, json: savedReport })
      } else if (failList) {
        await route.fulfill({ status: 503, json: {
          error: { code: 'test_unavailable', message: 'P15 受控查询失败', request_id: 'p15-test' },
        } })
      } else {
        await route.fulfill({ json: {
          items: savedReport ? [savedReport] : [], total: savedReport ? 1 : 0,
          page: 1, page_size: 20, total_pages: savedReport ? 1 : 0,
        } })
      }
    })
    await page.goto(`${frontendUrl}/login`)
    await login(users[0])
    await page.getByRole('link', { name: '数据', exact: true }).click()
    const started = Date.now()
    await page.getByRole('button', { name: '生成报告', exact: true }).click()
    const loading = page.getByRole('button', { name: '正在生成', exact: true })
    await loading.waitFor()
    assert.equal(await loading.isDisabled(), true)
    await page.locator('.analytics-report-summary').waitFor({ timeout: 15000 })
    assert.ok(Date.now() - started >= 6000)
    assert.equal(postCount, 1)
    console.log('通过：延迟报告成功，生成中禁止重复提交')

    phase = '退出销毁旧会话'
    const beforeLogout = await page.evaluate(() => performance.timeOrigin)
    await page.getByRole('button', { name: '退出', exact: true }).click()
    await page.waitForURL(url => url.pathname === '/login')
    await page.getByRole('button', { name: '登录', exact: true }).waitFor()
    assert.notEqual(await page.evaluate(() => performance.timeOrigin), beforeLogout)
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), tokenKey), null)

    phase = '错误密码不触发公开页重载'
    await page.getByLabel('用户名或邮箱').fill(users[1].username)
    await page.getByLabel('密码', { exact: true }).fill('incorrect-p15-test-password')
    const beforeWrongPassword = await page.evaluate(() => performance.timeOrigin)
    const rejected = page.waitForResponse(response => response.url().endsWith('/auth/login'))
    await page.getByRole('button', { name: '登录', exact: true }).click()
    assert.equal((await rejected).status(), 401)
    await page.getByRole('alert').waitFor()
    assert.equal(await page.evaluate(() => performance.timeOrigin), beforeWrongPassword)

    phase = '第二账号查询失败不显示旧报告'
    await login(users[1])
    savedReport = null
    failList = true
    await page.getByRole('link', { name: '数据', exact: true }).click()
    await page.getByText('P15 受控查询失败', { exact: true }).waitFor()
    assert.equal(await page.locator('.analytics-report-summary').count(), 0)
    assert.equal((await page.locator('body').innerText()).includes(users[0].username), false)
    mkdirSync(evidence, { recursive: true })
    await page.screenshot({ path: path.join(evidence, 'session-isolation.png'), fullPage: true })
    console.log('通过：退出完整导航、错误密码反馈、跨账号失败态隔离')

    phase = '受保护页面 401 清理'
    const beforeExpired = await page.evaluate(() => performance.timeOrigin)
    await page.evaluate(key => sessionStorage.setItem(key, 'invalid-p15-test-token'), tokenKey)
    await page.getByRole('link', { name: '我的桌面', exact: true }).click()
    await page.waitForURL(url => url.pathname === '/login')
    await page.getByRole('button', { name: '登录', exact: true }).waitFor()
    assert.notEqual(await page.evaluate(() => performance.timeOrigin), beforeExpired)
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), tokenKey), null)
    assert.equal(errors.length, 0)
    console.log('通过：受保护请求 401 清理 Token 和旧会话；无页面脚本错误')
  } catch (error) {
    mkdirSync(evidence, { recursive: true })
    await page.screenshot({ path: path.join(evidence, 'session-failure.png'), fullPage: true })
    console.error(`失败阶段：${phase}；页面路径：${new URL(page.url()).pathname}`)
    throw error
  } finally {
    await browser.close()
    if (users.length) {
      // 同时核对本次 ID 和随机用户名，不删除共享环境中的其他账号。
      execFileSync(path.join(backend, '.venv/Scripts/python.exe'), ['-X', 'utf8', '-c',
        cleanupCode,
        JSON.stringify(users.map(({ id, username }) => ({ id, username }))),
      ], { cwd: backend, stdio: 'inherit' })
    }
  }
}

main().catch(() => { process.exitCode = 1 })
