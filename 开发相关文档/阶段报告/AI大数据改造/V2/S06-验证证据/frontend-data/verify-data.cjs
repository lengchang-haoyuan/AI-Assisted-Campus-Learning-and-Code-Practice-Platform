const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const root = 'C:/Users/Administrator/Desktop/毕业设计/ScholarHub'
const vue = require(path.join(root, 'frontend/node_modules/vue'))
const ts = require(path.join(root, 'frontend/node_modules/typescript'))
let checks = 0
function check(condition, message) { assert.ok(condition, message); ++checks }
function equal(actual, expected, message) { assert.deepEqual(actual, expected, message); ++checks }
function moduleFrom(relative, deps) {
  const result = ts.transpileModule(fs.readFileSync(path.join(root, relative), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  })
  const module = { exports: {} }
  vm.runInNewContext(result.outputText, {
    exports: module.exports, module,
    require(name) { if (!(name in deps)) throw new Error(`Unexpected import: ${name}`); return deps[name] },
    AbortController, Intl, Date, Number, Object, Error,
  }, { filename: relative })
  return module.exports
}
const payload = JSON.parse(fs.readFileSync(path.join(root,
  '开发相关文档/阶段报告/AI大数据改造/V2/S05-发布输入/v2-controlled/payload.json'), 'utf8'))
function detail(id = '77e12daa-c693-4c47-8ef8-e7c5b78b1395') {
  const { owner_user_id, source_counts, dataset_id, snapshot_id, job_id, ...value } = structuredClone(payload)
  return { ...value, batch_id: id, published_at: '2026-10-20T08:00:00Z', source: { dataset_id, snapshot_id, job_id } }
}
const main = detail()
const second = detail('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
const newest = detail('cccccccc-cccc-4ccc-8ccc-cccccccccccc')
const listQueue = []
const detailQueue = []
function pending(queue, args) {
  return new Promise((resolve, reject) => queue.push({ args, resolve, reject }))
}
const api = moduleFrom('frontend/src/api/offlineAnalytics.ts', {
  './client': { apiClient: { get: (...args) => pending(apiQueue, args) } },
})
const apiQueue = []
const auth = vue.reactive({ token: 'test-session-a', currentUser: { id: 3 } })
const logic = moduleFrom('frontend/src/composables/useOfflineAnalytics.ts', {
  vue,
  '@/api/errors': { getApiErrorStatus: cause => cause.status ?? null, getApiErrorMessage: (_cause, fallback) => fallback },
  '@/api/offlineAnalytics': {
    ...api,
    listOfflineBatches: (...args) => pending(listQueue, args),
    getOfflineBatch: (...args) => pending(detailQueue, args),
  },
  '@/stores/auth': { useAuthStore: () => auth },
})
const flush = () => new Promise(resolve => setTimeout(resolve, 0))
const page = (...items) => ({ items, total: items.length, page: 1, page_size: 20, empty_reason: items.length ? null : 'no_matching_batch' })

;(async () => {
  const scope = vue.effectScope()
  const state = scope.run(() => logic.useOfflineAnalytics())
  equal(listQueue.length, 1, 'authenticated mount requests a list')
  equal(listQueue[0].args[0].dataset_kind, 'business', 'normal data is the default')
  listQueue.shift().resolve(page(main))
  await flush()
  equal(detailQueue[0].args[0], main.batch_id, 'initial selection uses the returned batch')
  detailQueue.shift().resolve(main)
  await flush()
  equal(state.selectedBatchId.value, main.batch_id, 'a complete detail selects its own batch')
  equal(state.detail.value.records_summary.known_minutes, 75, 'known recorded minutes retained')

  const refreshing = state.refreshList()
  const selectSecond = state.selectBatch(second.batch_id)
  listQueue.shift().resolve(page(newest, main))
  await flush()
  equal(detailQueue.length, 1, 'a list response cannot override a newer explicit selection')
  detailQueue.shift().resolve(second)
  await Promise.all([refreshing, selectSecond])
  equal(state.detail.value.batch_id, second.batch_id, 'the explicitly selected detail wins')

  const failedSelection = state.selectBatch(newest.batch_id)
  equal(state.detail.value.batch_id, second.batch_id, 'pending selection keeps the prior complete detail')
  equal(state.pendingBatchId.value, newest.batch_id, 'pending and displayed batch are separate')
  detailQueue.shift().reject({ status: 503 })
  await failedSelection
  equal(state.selectedBatchId.value, second.batch_id, 'failed selection preserves the matching old title')
  check(state.staleMessage.value.includes('上一成功批次'), 'failed selection explains retained data')
  const retry = state.retry()
  equal(detailQueue[0].args[0], newest.batch_id, 'retry targets the failed selected batch')
  detailQueue.shift().resolve(newest)
  await retry
  equal(state.detail.value.batch_id, newest.batch_id, 'retry replaces all facts together')
  equal(state.staleMessage.value, null, 'success clears the stale notice')

  const refreshHistory = state.refreshList()
  listQueue.shift().resolve(page(main))
  await flush()
  equal(detailQueue[0].args[0], newest.batch_id, 'refresh does not replace the chosen history with the list first item')
  detailQueue.shift().resolve(newest)
  await refreshHistory

  const pendingDetail = state.selectBatch(main.batch_id)
  const deniedList = state.refreshList()
  listQueue.shift().reject({ status: 403 })
  await deniedList
  equal(state.detail.value, null, 'permission denial clears private displayed detail')
  check(state.forbiddenMessage.value !== null, 'permission denial has an actionable notice')
  detailQueue.shift().resolve(main)
  await pendingDetail
  equal(state.detail.value, null, 'late detail cannot restore data after permission failure')

  const late = state.selectBatch(main.batch_id)
  auth.token = null
  auth.currentUser = null
  equal(state.detail.value, null, 'logout clears data synchronously')
  equal(state.batches.value.length, 0, 'logout clears the batch cache')
  detailQueue.shift().resolve(main)
  await late
  equal(state.detail.value, null, 'old-session response is ignored after logout')
  auth.token = 'test-session-b'
  auth.currentUser = { id: 4 }
  equal(listQueue.length, 1, 'new account starts a distinct list request')
  listQueue.shift().resolve(page(second))
  await flush()
  detailQueue.shift().resolve(second)
  await flush()
  equal(state.detail.value.batch_id, second.batch_id, 'new account only displays its own response')

  const failedFilter = state.applyPeriod('2026-10-19', '2026-10-20')
  listQueue.shift().reject({ status: 503 })
  await failedFilter
  equal(state.detail.value.batch_id, second.batch_id, 'failed date filter preserves the complete old batch')
  const retryFilter = state.retry()
  listQueue.shift().resolve(page(main))
  await flush()
  equal(detailQueue[0].args[0], main.batch_id, 'filter retry applies the filter selection rather than silently restoring unrelated history')
  detailQueue.shift().resolve(main)
  await retryFilter
  equal(state.detail.value.batch_id, main.batch_id, 'filter retry replaces all facts with the matching batch')

  const invalidDate = state.applyPeriod('2026-02-31', '2026-03-02')
  await invalidDate
  equal(listQueue.length, 0, 'invalid calendar date is not sent')
  const emptyPeriod = state.applyPeriod('2025-01-01', '2025-01-02')
  equal(listQueue[0].args[0].period_start, '2025-01-01', 'date filters apply to the list, not detail arithmetic')
  listQueue.shift().resolve(page())
  await emptyPeriod
  equal(state.detail.value, null, 'an empty explicit filter clears a previously displayed batch')
  equal(state.emptyReason.value, 'no_matching_batch', 'empty-window meaning remains explicit')
  scope.stop()

  const fixedScope = vue.effectScope()
  const fixed = fixedScope.run(() => logic.useOfflineAnalytics({ initialKind: 'controlled', initialBatchId: main.batch_id }))
  equal(listQueue[0].args[0].dataset_kind, 'controlled', 'initial URL can explicitly select controlled samples')
  equal(detailQueue[0].args[0], main.batch_id, 'initial URL directly requests the fixed approved batch')
  listQueue.shift().resolve(page(newest))
  await flush()
  equal(detailQueue.length, 1, 'initial list first fixture does not replace the requested URL batch')
  detailQueue.shift().resolve(main)
  await flush()
  equal(fixed.detail.value.batch_id, main.batch_id, 'fixed initial detail and all charts retain the same batch')
  fixedScope.stop()
  const invalidScope = vue.effectScope()
  const invalid = invalidScope.run(() => logic.useOfflineAnalytics({ initialBatchId: '../../arbitrary' }))
  equal(listQueue.length + detailQueue.length, 0, 'invalid URL batch never requests an arbitrary path or a different batch')
  check(invalid.error.value.includes('格式无效'), 'invalid initial batch explains the rejected selection')
  invalidScope.stop()

  equal(logic.formatRatio({ numerator: 199, denominator: 200, percent: '99.500000', display: '99.5%' }), '99.5%', '199/200 is not rounded to 100')
  equal(logic.formatRatio({ numerator: 0, denominator: 0, percent: null, display: '无样本' }), '无样本', 'an empty denominator is not zero percent')
  const chart = logic.buildOfflineChartData(main)
  equal(chart.sources.find(item => item.name === '可信教学来源').value, 2, 'trusted sources use published relationship counts')
  equal(chart.tasks.reduce((sum, item) => sum + item.value, 0), 4, 'cancelled tasks remain in the denominator')
  const allUnknown = detail()
  allUnknown.daily = [{ ...allUnknown.daily[0], records: 1, known_duration_count: 0, known_minutes: 0, missing_duration_count: 1, known_zero_count: 0 }]
  equal(logic.buildOfflineChartData(allUnknown).minutes[0], null, 'unknown-duration day produces a gap')
  allUnknown.daily[0].known_duration_count = 1
  allUnknown.daily[0].known_zero_count = 1
  allUnknown.daily[0].missing_duration_count = 0
  equal(logic.buildOfflineChartData(allUnknown).minutes[0], 0, 'known zero remains visible zero')
  const insights = logic.buildProcessInsights(main)
  equal(insights.length, 5, 'only the five frozen deterministic rules are explained')
  equal(insights.find(item => item.id === 'first_pass_counterexample').numerator, 1, 'first-pass counterexample is preserved')
  check(insights.find(item => item.id === 'revision_observed').boundary.includes('不能'), 'revision explanation preserves the noncausal boundary')
  check(logic.formatBatchInstant('2026-10-19T16:00:00Z').includes('2026/10/20'), 'UTC midnight converts to the batch business day')

  const goodRequest = api.getOfflineBatch(main.batch_id)
  apiQueue.shift().resolve({ data: main })
  equal((await goodRequest).batch_id, main.batch_id, 'supported and reconciled response is accepted')
  const oldVersion = api.getOfflineBatch(main.batch_id)
  apiQueue.shift().resolve({ data: { ...main, metric_version: 'legacy-0.9' } })
  await assert.rejects(oldVersion, api.OfflineAnalyticsCompatibilityError); ++checks
  const unsafe = api.getOfflineBatch(main.batch_id)
  apiQueue.shift().resolve({ data: { ...main, records_summary: { ...main.records_summary, known_minutes: Number.MAX_SAFE_INTEGER + 1 } } })
  await assert.rejects(unsafe, api.OfflineAnalyticsCompatibilityError); ++checks
  const badQuality = api.getOfflineBatch(main.batch_id)
  apiQueue.shift().resolve({ data: { ...main, quality: { fatal_errors: 1, reconciled: false } } })
  await assert.rejects(badQuality, api.OfflineAnalyticsCompatibilityError); ++checks
  console.log(JSON.stringify({ passed: true, checks, scope: 'S06 frontend data layer and deterministic view model', api: 'mock boundary only; no database or model calls' }))
})().catch(error => { console.error(error); process.exitCode = 1 })
