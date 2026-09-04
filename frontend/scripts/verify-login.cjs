// 使用已有外部 Playwright；不创建账号，不修改数据库，不调用模型。
const assert = require('node:assert/strict')
const { mkdirSync } = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const evidence = path.resolve(__dirname, '../../开发相关文档/测试证据/登录页面优化')

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.SCHOLARHUB_BROWSER_PATH,
  })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.name))
  let phase = '初始加载'
  try {
    await page.clock.install()
    await page.goto('http://127.0.0.1:5173/login')
    const slider = page.getByRole('slider', { name: '滑块验证' })
    const ready = page.locator('.slider-captcha.is-ready')
    await ready.waitFor()
    mkdirSync(evidence, { recursive: true })
    await page.getByRole('button', { name: '登录', exact: true }).click({ trial: true })
    await page.screenshot({ path: path.join(evidence, '桌面登录页.png'), fullPage: true })

    phase = '主题切换和密码显隐'
    await page.getByRole('tab', { name: '校园代码社区' }).click()
    await page.getByRole('img', { name: '校园地图与定位图钉插画' }).waitFor()
    await page.getByRole('tab', { name: '校园代码社区' }).press('Home')
    assert.equal(await page.getByRole('tab', { name: '项目实践' }).getAttribute('aria-selected'), 'true')
    await page.getByRole('button', { name: '显示密码' }).press('Enter')
    assert.equal(await page.getByLabel('密码', { exact: true }).getAttribute('type'), 'text')
    await page.getByRole('button', { name: '隐藏密码' }).press('Enter')
    assert.equal(await page.getByLabel('密码', { exact: true }).getAttribute('type'), 'password')
    const heights = await page.locator('.el-input').evaluateAll(inputs => inputs.map(input => input.getBoundingClientRect().height))
    assert.equal(heights[0], heights[1])

    phase = '未验证不能提交登录'
    let loginRequests = 0
    page.on('request', request => {
      if (request.url().endsWith('/auth/login')) loginRequests++
    })
    await page.getByLabel('用户名或邮箱').fill('ui_validation_only')
    await page.getByLabel('密码', { exact: true }).fill('not-a-real-password')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await page.getByText('请先完成下方滑块验证', { exact: true }).waitFor()
    assert.equal(loginRequests, 0)
    await page.getByLabel('用户名或邮箱').clear()
    await page.getByLabel('密码', { exact: true }).clear()

    async function drag(ratio) {
      await ready.waitFor()
      await slider.click({ trial: true })
      const handle = await slider.boundingBox()
      const track = await page.locator('.slider-captcha__track').boundingBox()
      assert.ok(handle && track)
      const start = handle.x + handle.width / 2
      const end = track.x + track.width - handle.width / 2 - 5
      const y = handle.y + handle.height / 2
      await page.mouse.move(start, y)
      await page.mouse.down()
      for (let step = 1; step <= 20; step++) {
        await page.mouse.move(start + (end - start) * ratio * step / 20, y)
        await new Promise(resolve => setTimeout(resolve, 30))
      }
      await page.mouse.up()
    }

    phase = '部分拖动回弹和真实验证'
    await drag(0.5)
    assert.equal(await slider.getAttribute('aria-valuenow'), '0')
    await drag(1)
    await page.getByText('验证通过', { exact: true }).waitFor()
    assert.equal(await slider.getAttribute('aria-valuenow'), '100')
    await page.screenshot({ path: path.join(evidence, '滑块验证通过.png'), fullPage: true })

    phase = '前端到期提醒'
    // 这里只推进浏览器时钟；服务端过期由 test_slider_captcha 独立验证。
    await page.clock.fastForward(61000)
    await page.getByText('验证已过期，请刷新后重试', { exact: true }).waitFor()

    phase = '网络失败和恢复'
    await page.route('**/auth/slider/challenge', route => route.abort('failed'))
    await page.getByRole('button', { name: '刷新', exact: true }).click()
    await page.locator('.slider-captcha.is-error').waitFor()
    assert.equal(await slider.getAttribute('aria-disabled'), 'true')
    await page.unroute('**/auth/slider/challenge')
    await page.getByRole('button', { name: '刷新', exact: true }).click()
    await ready.waitFor()
    await new Promise(resolve => setTimeout(resolve, 600))
    await slider.press('End')
    await slider.press('Enter')
    await page.getByText('验证通过', { exact: true }).waitFor()

    phase = '窄屏布局和减少动态效果'
    await page.reload()
    await ready.waitFor()
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 844 })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      if (width === 390) {
        await page.screenshot({ path: path.join(evidence, '手机登录页.png'), fullPage: true })
      }
    }
    await page.emulateMedia({ reducedMotion: 'reduce' })
    assert.equal(await page.locator('.login-form-surface').evaluate(element => getComputedStyle(element).animationName), 'none')
    assert.equal(errors.length, 0)
    console.log('通过：主题切换、键盘显隐、输入框等高、未验证阻止登录、部分拖动回弹、真实滑块校验、到期提醒、网络恢复、键盘验证、320/390/768/1440px 无横向溢出、减少动态效果；无页面脚本错误')
  } catch (error) {
    console.error(`失败阶段：${phase}；错误类型：${error.name}`)
    throw error
  } finally {
    await browser.close()
  }
}

main().catch(() => { process.exitCode = 1 })
