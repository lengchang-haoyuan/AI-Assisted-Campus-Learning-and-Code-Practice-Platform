<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsCoreOption } from 'echarts/core'

import EChartPanel from '@/components/EChartPanel.vue'
import LiquidTabs from '@/components/LiquidTabs.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import { useAnalyticsStore } from '@/stores/analytics'
import type {
  LearningReportResponse,
  TechnologyDimensionKey,
  TrendDays,
} from '@/types/analytics'

const analyticsStore = useAnalyticsStore()
const rangeValue = ref('7')
const technologyKey = ref<TechnologyDimensionKey>('language')
const utcOffsetMinutes = -new Date().getTimezoneOffset()

function localDateValue(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const todayDate = new Date()
const periodEnd = ref(localDateValue(todayDate))
const initialStart = new Date(todayDate)
initialStart.setDate(initialStart.getDate() - 6)
const periodStart = ref(localDateValue(initialStart))

const selectedDays = computed<TrendDays>(() => rangeValue.value === '30' ? 30 : 7)
const currentTechnology = computed(() => analyticsStore.technologies?.dimensions.find(
  (dimension) => dimension.key === technologyKey.value,
) ?? null)

const trendHasData = computed(() => analyticsStore.trend?.items.some((item) => (
  item.visitors + item.completed_task_users + item.community_interactions > 0
)) ?? false)
const projectTrendHasData = computed(() => analyticsStore.trend?.items.some((item) => (
  item.projects_created + item.projects_completed + item.projects_published > 0
)) ?? false)
const statusHasData = computed(() => analyticsStore.projects?.statuses.some(
  (item) => item.count > 0,
) ?? false)
const technologyHasData = computed(() => (currentTechnology.value?.items.length ?? 0) > 0)

const trendOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 520,
  color: ['#2867d8', '#19775f', '#d66e2c'],
  aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'axis' },
  legend: { top: 0, textStyle: { color: '#66747d' } },
  grid: {
    top: 48,
    right: 18,
    bottom: 34,
    left: 42,
    outerBoundsMode: 'same',
    outerBoundsContain: 'axisLabel',
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: analyticsStore.trend?.items.map((item) => item.date.slice(5)) ?? [],
    axisLabel: { color: '#66747d', hideOverlap: true },
    axisLine: { lineStyle: { color: '#d9e4e1' } },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: '#66747d' },
    splitLine: { lineStyle: { color: '#e6eeec' } },
  },
  series: [
    {
      name: '访问人数',
      type: 'line',
      smooth: 0.3,
      symbolSize: 7,
      data: analyticsStore.trend?.items.map((item) => item.visitors) ?? [],
    },
    {
      name: '完成任务人数',
      type: 'line',
      smooth: 0.3,
      symbolSize: 7,
      data: analyticsStore.trend?.items.map((item) => item.completed_task_users) ?? [],
    },
    {
      name: '社区互动',
      type: 'line',
      smooth: 0.3,
      symbolSize: 7,
      data: analyticsStore.trend?.items.map((item) => item.community_interactions) ?? [],
    },
  ],
}))

const projectTrendOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 520,
  color: ['#2867d8', '#19775f', '#f1a468'],
  aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { top: 0, textStyle: { color: '#66747d' } },
  grid: {
    top: 48,
    right: 18,
    bottom: 34,
    left: 42,
    outerBoundsMode: 'same',
    outerBoundsContain: 'axisLabel',
  },
  xAxis: {
    type: 'category',
    data: analyticsStore.trend?.items.map((item) => item.date.slice(5)) ?? [],
    axisLabel: { color: '#66747d', hideOverlap: true },
    axisLine: { lineStyle: { color: '#d9e4e1' } },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: '#66747d' },
    splitLine: { lineStyle: { color: '#e6eeec' } },
  },
  series: [
    {
      name: '新建',
      type: 'bar',
      barMaxWidth: 16,
      data: analyticsStore.trend?.items.map((item) => item.projects_created) ?? [],
    },
    {
      name: '完成',
      type: 'bar',
      barMaxWidth: 16,
      data: analyticsStore.trend?.items.map((item) => item.projects_completed) ?? [],
    },
    {
      name: '发布',
      type: 'bar',
      barMaxWidth: 16,
      data: analyticsStore.trend?.items.map((item) => item.projects_published) ?? [],
    },
  ],
}))

const projectStatusLabels: Record<string, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  published: '已发布',
  archived: '已归档',
}

const statusOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 520,
  color: ['#9aa8ae', '#2867d8', '#19775f', '#f1a468', '#7355a8'],
  aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { color: '#66747d' } },
  series: [
    {
      name: '项目状态',
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      label: { color: '#17232f', formatter: '{b}\n{c}' },
      data: analyticsStore.projects?.statuses.map((item) => ({
        name: projectStatusLabels[item.status] ?? item.status,
        value: item.count,
      })) ?? [],
    },
  ],
}))

const technologyOption = computed<EChartsCoreOption>(() => ({
  animationDuration: 520,
  color: ['#2867d8'],
  aria: { enabled: true, decal: { show: true } },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: {
    top: 10,
    right: 38,
    bottom: 28,
    left: 20,
    outerBoundsMode: 'same',
    outerBoundsContain: 'axisLabel',
  },
  xAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: '#66747d' },
    splitLine: { lineStyle: { color: '#e6eeec' } },
  },
  yAxis: {
    type: 'category',
    inverse: true,
    data: currentTechnology.value?.items.map((item) => item.name) ?? [],
    axisLabel: { color: '#17232f', width: 120, overflow: 'truncate' },
    axisLine: { lineStyle: { color: '#d9e4e1' } },
  },
  series: [
    {
      name: currentTechnology.value?.label ?? '技术栈',
      type: 'bar',
      barMaxWidth: 22,
      label: { show: true, position: 'right', color: '#66747d' },
      data: currentTechnology.value?.items.map((item) => item.count) ?? [],
    },
  ],
}))

const reportStatusLabels: Record<LearningReportResponse['status'], string> = {
  pending: '生成中',
  completed: '已完成',
  failed: '可重试',
}

const performanceLabels: Record<string, string> = {
  starting: '起步阶段',
  steady: '节奏稳定',
  strong: '表现良好',
  excellent: '表现出色',
}

function formatDate(dateValue: string): string {
  return dateValue.replaceAll('-', '.')
}

async function loadDashboard(): Promise<void> {
  try {
    await analyticsStore.fetchDashboard(selectedDays.value, utcOffsetMinutes)
  } catch {
    // Store 已保存可重试提示。
  }
}

async function loadReports(): Promise<void> {
  try {
    await analyticsStore.fetchReports()
  } catch {
    // Store 已保存可重试提示。
  }
}

async function createReport(): Promise<void> {
  if (!periodStart.value || !periodEnd.value || periodEnd.value < periodStart.value) {
    ElMessage.warning('请选择有效的报告日期范围')
    return
  }
  try {
    const report = await analyticsStore.createReport({
      period_start: periodStart.value,
      period_end: periodEnd.value,
      timezone_offset_minutes: utcOffsetMinutes,
    })
    if (report.status === 'completed') {
      ElMessage.success('学习报告已生成并保存')
    } else {
      ElMessage.warning(report.error?.message ?? '报告生成失败，可稍后重试')
    }
  } catch {
    // Store 已保存错误，页面保留当前内容。
  }
}

watch(rangeValue, () => {
  void loadDashboard()
})

onMounted(() => {
  void Promise.all([loadDashboard(), loadReports()])
})
</script>

<template>
  <div class="page-shell analytics-page">
    <header class="analytics-header">
      <div>
        <h1>学习与社区数据</h1>
        <p>统计口径来自数据库 UTC 时间，按当前浏览器时区展示；图表不会补造历史活动。</p>
      </div>
      <LiquidTabs
        v-model="rangeValue"
        :options="[{ value: '7', label: '近 7 日' }, { value: '30', label: '近 30 日' }]"
        ariaLabel="统计时间范围"
      />
    </header>

    <div v-if="analyticsStore.error" class="inline-alert is-error" role="alert">
      <span>{{ analyticsStore.error }}</span>
      <button type="button" @click="loadDashboard">重试</button>
    </div>

    <div v-if="analyticsStore.loading && !analyticsStore.today" class="analytics-loading" aria-label="统计数据加载中">
      <span v-for="index in 8" :key="index" />
    </div>

    <template v-else-if="analyticsStore.today && analyticsStore.trend && analyticsStore.projects && analyticsStore.technologies">
      <section class="analytics-metrics" aria-label="今日核心统计">
        <article>
          <NumberRoller :value="analyticsStore.today.visitors" />
          <strong>今日访问人数</strong>
          <small>按登录用户去重</small>
        </article>
        <article>
          <NumberRoller :value="analyticsStore.today.completed_task_users" />
          <strong>完成任务人数</strong>
          <small>今日完成至少一项</small>
        </article>
        <article>
          <NumberRoller :value="analyticsStore.today.project_total" />
          <strong>平台项目</strong>
          <small>今日新增 {{ analyticsStore.today.projects_created }}</small>
        </article>
        <article>
          <NumberRoller :value="analyticsStore.today.published_project_total" />
          <strong>已发布项目</strong>
          <small>今日发布 {{ analyticsStore.today.projects_published }}</small>
        </article>
        <article>
          <NumberRoller :value="analyticsStore.today.community_interactions" />
          <strong>社区互动</strong>
          <small>浏览、评论、点赞与收藏</small>
        </article>
        <article>
          <NumberRoller :value="`${analyticsStore.projects.average_progress}%`" />
          <strong>项目平均进度</strong>
          <small>{{ analyticsStore.projects.completed }} 个项目已完成</small>
        </article>
      </section>

      <div class="analytics-chart-grid">
        <section class="analytics-figure analytics-figure--wide">
          <div class="analytics-figure__heading">
            <div><h2>学习与社区活跃趋势</h2><p>人数按天去重，社区互动按事件计数。</p></div>
            <span>{{ analyticsStore.trend.start_date }} 至 {{ analyticsStore.trend.end_date }}</span>
          </div>
          <EChartPanel
            :option="trendOption"
            :empty="!trendHasData"
            empty-text="这一时间范围内还没有访问、任务完成或社区互动。"
            ariaLabel="学习与社区活跃折线图"
          />
        </section>

        <section class="analytics-figure analytics-figure--wide">
          <div class="analytics-figure__heading">
            <div><h2>项目变化趋势</h2><p>完成时间从 P14 开始准确记录，不回填旧状态。</p></div>
          </div>
          <EChartPanel
            :option="projectTrendOption"
            :empty="!projectTrendHasData"
            empty-text="这一时间范围内还没有项目新建、完成或发布事件。"
            ariaLabel="项目变化柱状图"
          />
        </section>

        <section class="analytics-figure">
          <div class="analytics-figure__heading">
            <div><h2>项目状态分布</h2><p>当前数据库中的项目状态快照。</p></div>
          </div>
          <EChartPanel
            :option="statusOption"
            :empty="!statusHasData"
            empty-text="创建项目后即可看到状态分布。"
            ariaLabel="项目状态环形图"
          />
        </section>

        <section class="analytics-figure analytics-tech-figure">
          <div class="analytics-figure__heading">
            <div><h2>技术栈使用情况</h2><p>按已填写技术字段聚合，不把空值计入比例。</p></div>
          </div>
          <div class="analytics-tech-tabs">
            <LiquidTabs
              v-model="technologyKey"
              :options="analyticsStore.technologies.dimensions.map((item) => ({ value: item.key, label: item.label }))"
              ariaLabel="技术栈维度"
            />
          </div>
          <EChartPanel
            :option="technologyOption"
            :empty="!technologyHasData"
            empty-text="项目尚未填写这一类技术栈。"
            ariaLabel="技术栈使用条形图"
          />
        </section>
      </div>

      <section class="analytics-reports" aria-labelledby="learning-report-title">
        <div class="analytics-report-control">
          <div>
            <h2 id="learning-report-title">AI 学习报告</h2>
            <p>只提交当前用户的聚合指标，失败报告保留状态并允许相同周期重试。</p>
          </div>
          <form class="analytics-report-form" @submit.prevent="createReport">
            <label class="field">
              开始日期
              <input v-model="periodStart" type="date" :max="periodEnd" required />
            </label>
            <label class="field">
              结束日期
              <input v-model="periodEnd" type="date" :min="periodStart" :max="localDateValue(todayDate)" required />
            </label>
            <button class="primary-command" type="submit" :disabled="analyticsStore.generating">
              {{ analyticsStore.generating ? '正在生成' : '生成报告' }}
            </button>
          </form>

          <div v-if="analyticsStore.reportError" class="inline-alert is-error" role="alert">
            <span>{{ analyticsStore.reportError }}</span>
            <button type="button" @click="loadReports">重试</button>
          </div>

          <div class="analytics-report-history">
            <div class="panel-title-row">
              <h3>历史报告</h3>
              <span>{{ analyticsStore.reports.total }} 份</span>
            </div>
            <div v-if="analyticsStore.reportLoading" class="analytics-report-loading" aria-label="报告加载中">
              <span v-for="index in 3" :key="index" />
            </div>
            <div v-else-if="analyticsStore.reports.items.length" class="analytics-report-list">
              <button
                v-for="report in analyticsStore.reports.items"
                :key="report.id"
                type="button"
                :class="{ 'is-active': analyticsStore.selectedReport?.id === report.id }"
                @click="analyticsStore.selectReport(report)"
              >
                <span><strong>{{ formatDate(report.period_start) }}</strong> 至 <strong>{{ formatDate(report.period_end) }}</strong></span>
                <small :data-status="report.status">{{ reportStatusLabels[report.status] }}</small>
              </button>
            </div>
            <div v-else class="analytics-report-empty">还没有学习报告</div>
          </div>
        </div>

        <article v-if="analyticsStore.selectedReport" class="analytics-report-detail">
          <header>
            <div>
              <span>{{ formatDate(analyticsStore.selectedReport.period_start) }} 至 {{ formatDate(analyticsStore.selectedReport.period_end) }}</span>
              <h2>{{ analyticsStore.selectedReport.status === 'completed' ? '阶段学习复盘' : '报告尚未生成' }}</h2>
            </div>
            <span class="status-chip" :data-status="analyticsStore.selectedReport.status">
              {{ reportStatusLabels[analyticsStore.selectedReport.status] }}
            </span>
          </header>

          <div v-if="analyticsStore.selectedReport.status === 'failed'" class="analytics-report-failure">
            <strong>本次生成没有产生报告内容</strong>
            <p>{{ analyticsStore.selectedReport.error?.message || analyticsStore.selectedReport.summary }}</p>
            <button class="secondary-command compact-command" type="button" @click="periodStart = analyticsStore.selectedReport.period_start; periodEnd = analyticsStore.selectedReport.period_end; createReport()">
              重试此周期
            </button>
          </div>

          <template v-else-if="analyticsStore.selectedReport.status === 'completed'">
            <p class="analytics-report-summary">{{ analyticsStore.selectedReport.summary }}</p>
            <div v-if="analyticsStore.selectedReport.structured_data" class="analytics-report-facts">
              <div><NumberRoller :value="analyticsStore.selectedReport.structured_data.total_learning_minutes" /><span>学习分钟</span></div>
              <div><NumberRoller :value="analyticsStore.selectedReport.structured_data.active_days" /><span>活跃天数</span></div>
              <div><NumberRoller :value="`${analyticsStore.selectedReport.structured_data.task_completion_rate}%`" /><span>任务完成率</span></div>
              <div><strong>{{ performanceLabels[analyticsStore.selectedReport.structured_data.performance_level] }}</strong><span>综合表现</span></div>
            </div>
            <div class="analytics-report-sections">
              <section><h3>阶段收获</h3><ul><li v-for="item in analyticsStore.selectedReport.achievement" :key="item">{{ item }}</li></ul></section>
              <section><h3>需要处理</h3><ul><li v-for="item in analyticsStore.selectedReport.problems" :key="item">{{ item }}</li></ul></section>
              <section><h3>下一步</h3><ul><li v-for="item in analyticsStore.selectedReport.suggestions" :key="item">{{ item }}</li></ul></section>
            </div>
          </template>
        </article>

        <div v-else class="analytics-report-placeholder">
          <strong>选择一段日期生成报告</strong>
          <p>报告会结合学习记录、任务、项目、Workflow、AI 使用和社区活动。</p>
        </div>
      </section>
    </template>
  </div>
</template>
