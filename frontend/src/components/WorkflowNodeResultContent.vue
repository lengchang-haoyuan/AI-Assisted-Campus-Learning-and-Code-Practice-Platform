<script setup lang="ts">
import { computed } from 'vue'

import type { JsonObject, JsonValue } from '@/types/workflow'
import '@/styles/workflow-node-result.css'

const props = defineProps<{
  result: JsonObject & { result_type: string; summary: string }
}>()

type ExtraField = { key: string; value: JsonValue }
interface Requirement {
  title: string
  description: string
  acceptanceCriteria: string[]
  extra: ExtraField[]
}
interface Technology {
  value: string
  reason: string
  extra: ExtraField[]
}
interface ArchitectureModule {
  name: string
  responsibility: string
  technology: string
  dependencies: string[]
  extra: ExtraField[]
}
interface DataFlow {
  source: string
  target: string
  data: string
  extra: ExtraField[]
}
interface Decision {
  title: string
  choice: string
  reason: string
  extra: ExtraField[]
}
type ResultSection = { key: string; title: string } & (
  | { kind: 'requirements'; items: Requirement[]; maxCriteria: number }
  | { kind: 'technology'; choice: Technology }
  | { kind: 'components'; items: ArchitectureModule[] }
  | { kind: 'flows'; items: DataFlow[] }
  | { kind: 'decisions'; items: Decision[] }
  | { kind: 'list'; items: string[]; ordered: boolean }
  | { kind: 'text'; value: string }
  | { kind: 'verdict'; value: string; tone: string }
  | { kind: 'fallback'; value: JsonValue }
)

const labels: Record<string, string> = {
  hints: '渐进提示', concepts: '相关知识点', next_step: '下一步', steps: '逐步讲解',
  complexity: '复杂度分析', pitfalls: '容易出错的地方', verdict: '静态评审结论', strengths: '做得好的地方',
  issues: '待改进问题', suggested_tests: '建议自己运行的测试', requirements: '需求与验收', features: '功能清单',
  constraints: '约束条件', language: '编程语言', framework: '主要框架', frontend: '前端方案', backend: '后端方案',
  database: '数据存储', style: '架构风格', components: '模块职责', data_flows: '数据流向', decisions: '设计决策',
  title: '目标', description: '说明', acceptance_criteria: '验收要求', value: '选择', reason: '选择理由',
  name: '名称', responsibility: '职责', technology: '技术', dependencies: '依赖模块', source: '来源',
  target: '目标', data: '传递数据', choice: '方案',
  looks_correct: '静态阅读暂未发现明显问题，仍需自测', needs_revision: '需要修改', insufficient_information: '信息不足',
}
const technologyKeys = new Set(['language', 'framework', 'frontend', 'backend', 'database'])
const orderedKeys = new Set(['hints', 'steps', 'suggested_tests'])

function label(key: string): string { return labels[key] ?? key }
function isObject(value: JsonValue): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}
function isStringArray(value: JsonValue | undefined): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}
function extraFields(value: JsonObject, known: string[]): ExtraField[] {
  return Object.entries(value).filter(([key]) => !known.includes(key)).map(([key, item]) => ({ key, value: item }))
}
function format(value: JsonValue): string {
  if (value === null) return '未提供'
  if (Array.isArray(value)) return value.length ? value.map((item, index) => `${index + 1}. ${format(item)}`).join('\n') : '无'
  if (isObject(value)) return Object.entries(value).map(([key, item]) => `${label(key)}：${format(item)}`).join('\n') || '无'
  return typeof value === 'string' ? value : String(value)
}

function parseRequirements(value: JsonValue): Requirement[] | null {
  if (!Array.isArray(value)) return null
  const items: Requirement[] = []
  for (const item of value) {
    if (!isObject(item) || typeof item.title !== 'string' || typeof item.description !== 'string' || !isStringArray(item.acceptance_criteria)) return null
    items.push({ title: item.title, description: item.description, acceptanceCriteria: item.acceptance_criteria, extra: extraFields(item, ['title', 'description', 'acceptance_criteria']) })
  }
  return items
}
function parseModules(value: JsonValue): ArchitectureModule[] | null {
  if (!Array.isArray(value)) return null
  const items: ArchitectureModule[] = []
  for (const item of value) {
    if (!isObject(item) || typeof item.name !== 'string' || typeof item.responsibility !== 'string' || typeof item.technology !== 'string' || !isStringArray(item.dependencies)) return null
    items.push({ name: item.name, responsibility: item.responsibility, technology: item.technology, dependencies: item.dependencies, extra: extraFields(item, ['name', 'responsibility', 'technology', 'dependencies']) })
  }
  return items
}
function parseFlows(value: JsonValue): DataFlow[] | null {
  if (!Array.isArray(value)) return null
  const items: DataFlow[] = []
  for (const item of value) {
    if (!isObject(item) || typeof item.source !== 'string' || typeof item.target !== 'string' || typeof item.data !== 'string') return null
    items.push({ source: item.source, target: item.target, data: item.data, extra: extraFields(item, ['source', 'target', 'data']) })
  }
  return items
}
function parseDecisions(value: JsonValue): Decision[] | null {
  if (!Array.isArray(value)) return null
  const items: Decision[] = []
  for (const item of value) {
    if (!isObject(item) || typeof item.title !== 'string' || typeof item.choice !== 'string' || typeof item.reason !== 'string') return null
    items.push({ title: item.title, choice: item.choice, reason: item.reason, extra: extraFields(item, ['title', 'choice', 'reason']) })
  }
  return items
}
function sectionFor(key: string, value: JsonValue): ResultSection {
  const base = { key, title: label(key) }
  if (key === 'requirements') {
    const items = parseRequirements(value)
    if (items) return { ...base, kind: 'requirements', items, maxCriteria: Math.max(1, ...items.map(item => item.acceptanceCriteria.length)) }
  }
  if (technologyKeys.has(key) && isObject(value) && typeof value.value === 'string' && typeof value.reason === 'string') {
    return { ...base, kind: 'technology', choice: { value: value.value, reason: value.reason, extra: extraFields(value, ['value', 'reason']) } }
  }
  if (key === 'components') {
    const items = parseModules(value)
    if (items) return { ...base, kind: 'components', items }
  }
  if (key === 'data_flows') {
    const items = parseFlows(value)
    if (items) return { ...base, kind: 'flows', items }
  }
  if (key === 'decisions') {
    const items = parseDecisions(value)
    if (items) return { ...base, kind: 'decisions', items }
  }
  if (key === 'verdict' && typeof value === 'string') return { ...base, kind: 'verdict', value: label(value), tone: ['looks_correct', 'needs_revision', 'insufficient_information'].includes(value) ? value : 'unknown' }
  if (isStringArray(value)) return { ...base, kind: 'list', items: value, ordered: orderedKeys.has(key) }
  if (typeof value === 'string') return { ...base, kind: 'text', value }
  return { ...base, kind: 'fallback', value }
}

const sections = computed(() => Object.entries(props.result)
  .filter(([key]) => key !== 'summary' && key !== 'result_type')
  .map(([key, value]) => sectionFor(key, value)))
</script>

<template>
  <div class="workflow-node-content" :data-result-type="result.result_type">
    <section class="workflow-node-content__summary" aria-label="分析摘要">
      <h5>分析摘要</h5>
      <p>{{ result.summary }}</p>
    </section>
    <div class="workflow-node-content__sections">
      <section v-for="section in sections" :key="section.key" class="workflow-node-content__section" :data-kind="section.kind" :data-field="section.key">
        <h5>{{ section.title }}<span v-if="section.kind === 'requirements' || section.kind === 'components' || section.kind === 'flows' || section.kind === 'decisions' || section.kind === 'list'">{{ section.items.length }} 项</span></h5>

        <template v-if="section.kind === 'requirements'">
          <figure v-if="section.items.length" class="workflow-acceptance-chart">
            <figcaption>验收项分布 <span>每项需求包含的验收要求数量</span></figcaption>
            <ul>
              <li v-for="(item, index) in section.items" :key="index">
                <span class="workflow-acceptance-chart__label">{{ item.title }}</span>
                <span class="workflow-acceptance-chart__track" aria-hidden="true"><span :style="{ width: `${item.acceptanceCriteria.length / section.maxCriteria * 100}%` }"></span></span>
                <strong>{{ item.acceptanceCriteria.length }} 项</strong>
              </li>
            </ul>
          </figure>
          <ol class="workflow-requirement-list">
            <li v-for="(item, index) in section.items" :key="index">
              <div class="workflow-requirement-list__heading"><span>{{ String(index + 1).padStart(2, '0') }}</span><h6>{{ item.title }}</h6></div>
              <p>{{ item.description }}</p>
              <div class="workflow-acceptance-list"><strong>验收要求</strong><ul><li v-for="(criterion, criterionIndex) in item.acceptanceCriteria" :key="criterionIndex">{{ criterion }}</li></ul><p v-if="!item.acceptanceCriteria.length" class="workflow-node-content__empty">无</p></div>
              <dl v-if="item.extra.length" class="workflow-content-extra"><div v-for="field in item.extra" :key="field.key"><dt>{{ label(field.key) }}</dt><dd>{{ format(field.value) }}</dd></div></dl>
            </li>
          </ol>
          <p v-if="!section.items.length" class="workflow-node-content__empty">无</p>
        </template>

        <template v-else-if="section.kind === 'technology'">
          <p class="workflow-technology-choice">{{ section.choice.value }}</p>
          <p class="workflow-technology-reason">{{ section.choice.reason }}</p>
          <dl v-if="section.choice.extra.length" class="workflow-content-extra"><div v-for="field in section.choice.extra" :key="field.key"><dt>{{ label(field.key) }}</dt><dd>{{ format(field.value) }}</dd></div></dl>
        </template>

        <template v-else-if="section.kind === 'components'">
          <div class="workflow-architecture-modules">
            <article v-for="(item, index) in section.items" :key="index">
              <h6>{{ item.name }}</h6>
              <p>{{ item.responsibility }}</p>
              <dl><div><dt>技术</dt><dd>{{ item.technology }}</dd></div><div><dt>依赖模块</dt><dd>{{ item.dependencies.length ? item.dependencies.join('、') : '无' }}</dd></div></dl>
              <dl v-if="item.extra.length" class="workflow-content-extra"><div v-for="field in item.extra" :key="field.key"><dt>{{ label(field.key) }}</dt><dd>{{ format(field.value) }}</dd></div></dl>
            </article>
          </div>
          <p v-if="!section.items.length" class="workflow-node-content__empty">无</p>
        </template>

        <template v-else-if="section.kind === 'flows'">
          <ul class="workflow-data-flows">
            <li v-for="(item, index) in section.items" :key="index">
              <div class="workflow-data-flows__route"><strong>{{ item.source }}</strong><span class="workflow-node-content__sr-only">流向</span><svg viewBox="0 0 32 16" fill="none" aria-hidden="true"><path d="M1 8h28m-7-6 7 6-7 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg><strong>{{ item.target }}</strong></div>
              <p><span>传递数据</span>{{ item.data }}</p>
              <dl v-if="item.extra.length" class="workflow-content-extra"><div v-for="field in item.extra" :key="field.key"><dt>{{ label(field.key) }}</dt><dd>{{ format(field.value) }}</dd></div></dl>
            </li>
          </ul>
          <p v-if="!section.items.length" class="workflow-node-content__empty">无</p>
        </template>

        <template v-else-if="section.kind === 'decisions'">
          <div class="workflow-design-decisions"><article v-for="(item, index) in section.items" :key="index"><h6>{{ item.title }}</h6><dl><div><dt>方案</dt><dd>{{ item.choice }}</dd></div><div><dt>选择理由</dt><dd>{{ item.reason }}</dd></div></dl><dl v-if="item.extra.length" class="workflow-content-extra"><div v-for="field in item.extra" :key="field.key"><dt>{{ label(field.key) }}</dt><dd>{{ format(field.value) }}</dd></div></dl></article></div>
          <p v-if="!section.items.length" class="workflow-node-content__empty">无</p>
        </template>

        <template v-else-if="section.kind === 'list'">
          <ol v-if="section.ordered && section.items.length" class="workflow-result-steps"><li v-for="(item, index) in section.items" :key="index"><span>{{ index + 1 }}</span><p>{{ item }}</p></li></ol>
          <ul v-else-if="section.items.length" class="workflow-content-list"><li v-for="(item, index) in section.items" :key="index">{{ item }}</li></ul>
          <p v-else class="workflow-node-content__empty">无</p>
        </template>

        <p v-else-if="section.kind === 'verdict'" class="workflow-review-verdict" :data-verdict="section.tone">{{ section.value }}</p>
        <p v-else-if="section.kind === 'text'" class="workflow-content-text">{{ section.value }}</p>
        <p v-else class="workflow-content-text">{{ format(section.value) }}</p>
      </section>
    </div>
  </div>
</template>
