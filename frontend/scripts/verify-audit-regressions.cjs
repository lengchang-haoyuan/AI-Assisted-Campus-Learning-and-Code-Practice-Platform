// 沿用现有外部 Playwright，所有 API 请求使用虚构响应，不访问数据库或模型。
const assert = require('node:assert/strict')
const { chromium } = require('playwright')

const baseUrl = process.env.SCHOLARHUB_FRONTEND_URL || 'http://127.0.0.1:4178'
const now = '2026-09-06T08:00:00Z'
const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.SCHOLARHUB_BROWSER_PATH,
  })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  const graphWrites = []
  const workflowWrites = []
  const recordWrites = []
  let graph = {
    workflow: {
      id: 11, project: { id: 7, name: '回归测试项目' }, name: '回归工作流',
      description: null, status: 'completed', version: 3, node_count: 1, edge_count: 0,
      created_at: now, updated_at: now,
    },
    nodes: [{
      id: 21, workflow_id: 11, node_key: 'teaching', node_type: 'exercise_hint',
      name: '教学节点', position_x: 150, position_y: 150, status: 'success',
      config: { instruction: '旧指令', expected_output: '提示', problem: '题意',
        student_code: 'print(1)', custom_option: '保留扩展字段' },
      context_version: 1, created_at: now, updated_at: now,
    }],
    edges: [],
  }
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => sessionStorage.setItem('scholarhub.access_token', 'audit-test-token'))
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const respond = data => route.fulfill({ status: 200, json: data })
    if (path.endsWith('/users/me')) return respond({
      id: 1, username: 'audit_student', email: 'audit@example.com', is_active: true,
      created_at: now, updated_at: now,
    })
    if (path.endsWith('/campus/me')) return respond({ membership: null })
    if (path.endsWith('/workflows/11/runs')) return respond(emptyPage)
    if (path.endsWith('/workflows/11/graph')) {
      if (method === 'PUT') {
        const input = request.postDataJSON()
        graphWrites.push(input)
        graph = {
          workflow: { ...graph.workflow, status: 'stale', version: graph.workflow.version + 1 },
          nodes: input.nodes.map((node, index) => ({ ...graph.nodes[index], ...node })),
          edges: input.edges,
        }
      }
      return respond(graph)
    }
    if (path.endsWith('/workflows/11') && method === 'PUT') {
      const input = request.postDataJSON()
      workflowWrites.push(input)
      graph.workflow = { ...graph.workflow, ...input }
      return respond(graph.workflow)
    }
    if (path.endsWith('/projects')) return respond({ ...emptyPage, items: [{
      id: 7, name: '回归测试项目', description: null, difficulty: 'beginner',
      status: 'in_progress', language: 'Python', progress: 0,
      owner: { id: 1, username: 'audit_student' }, tags: [], created_at: now, updated_at: now,
    }], total: 1, total_pages: 1 })
    if (path.endsWith('/workspace/records')) {
      if (method === 'POST') {
        const input = request.postDataJSON()
        recordWrites.push(input)
        return respond({ ...input, id: 1, project: { id: 7, name: '回归测试项目' }, created_at: now })
      }
      return respond(emptyPage)
    }
    errors.push(`未预期的 API 请求 ${method} ${path}`)
    return route.fulfill({ status: 500, json: { error: 'Unexpected test request' } })
  })

  try {
    await page.goto(`${baseUrl}/workflows/11`)
    await page.locator('.workflow-toolbar').waitFor()
    assert.equal(await page.locator('.workflow-save-state').innerText(), '已保存')
    await page.locator('.vue-flow__node').click()
    await page.getByLabel('分析指令', { exact: true }).fill('新指令')
    assert.equal(await page.locator('.workflow-save-state').innerText(), '有未保存修改')
    await page.getByRole('button', { name: '保存工作流', exact: true }).click()
    await page.getByText('请先应用当前节点的配置，再保存工作流。', { exact: true }).waitFor()
    assert.equal(graphWrites.length, 0)
    await page.getByRole('combobox', { name: /节点类型/ }).selectOption('requirements_analysis')
    await page.getByRole('button', { name: '应用配置', exact: true }).click()
    await page.getByLabel('工作流名称', { exact: true }).fill('修改后的工作流')
    await page.getByRole('button', { name: '保存工作流', exact: true }).click()
    await page.getByText('工作流已保存', { exact: true }).waitFor()
    assert.equal(graphWrites.length, 1)
    const config = graphWrites[0].nodes[0].config
    assert.equal(config.instruction, '新指令')
    assert.equal(config.custom_option, '保留扩展字段')
    assert.ok(!Object.hasOwn(config, 'problem'))
    assert.ok(!Object.hasOwn(config, 'student_code'))
    assert.deepEqual(workflowWrites, [{ name: '修改后的工作流' }])
    assert.equal(await page.locator('.workflow-save-state').innerText(), '已保存')

    for (const width of [1440, 820, 700, 620, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      const layout = await page.locator('.workflow-toolbar').evaluate(toolbar => {
        const bounds = toolbar.getBoundingClientRect()
        return {
          display: getComputedStyle(toolbar).display,
          fits: [...toolbar.children].every(child => {
            const rect = child.getBoundingClientRect()
            return rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1
          }),
        }
      })
      assert.equal(layout.display, 'flex', `工具栏布局 ${width}px`)
      assert.ok(layout.fits, `工具栏内容不能溢出 ${width}px`)
    }

    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto(`${baseUrl}/workspace/records`)
    await page.getByRole('button', { name: '记录学习', exact: true }).click()
    await page.getByLabel('记录标题', { exact: true }).fill('项目实践回归')
    const types = page.locator('.workspace-form select').first()
    assert.deepEqual(await types.locator('option').evaluateAll(options => options.map(x => x.value)),
      ['study', 'project'])
    await types.selectOption('project')
    await page.getByRole('button', { name: '保存记录', exact: true }).click()
    await page.getByText('项目实践记录必须关联项目', { exact: true }).waitFor()
    assert.equal(recordWrites.length, 0)
    await page.getByRole('combobox', { name: /关联项目/ }).selectOption('7')
    await page.getByRole('button', { name: '保存记录', exact: true }).click()
    await page.getByText('学习记录已保存', { exact: true }).waitFor()
    assert.equal(recordWrites.length, 1)
    assert.equal(recordWrites[0].project_id, 7)
    assert.deepEqual(errors, [])
    console.log('PASS: 配置脏状态、保存阻断、教学字段清理、扩展字段保留、重命名请求、5 种宽度和项目关联校验')
  } catch (error) {
    console.error({ url: page.url(), text: await page.locator('body').innerText(), errors })
    throw error
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
