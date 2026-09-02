<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { init, use, type EChartsCoreOption, type EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  LineChart,
  PieChart,
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = defineProps<{
  option: EChartsCoreOption
  empty: boolean
  emptyText: string
  ariaLabel: string
}>()

const chartElement = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

function renderChart(): void {
  if (!chartElement.value || props.empty) {
    chart?.clear()
    return
  }
  chart ??= init(chartElement.value, undefined, { renderer: 'canvas' })
  chart.setOption(props.option, { notMerge: true })
}

onMounted(() => {
  renderChart()
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartElement.value)
  }
})

watch(() => props.option, renderChart, { deep: true })
watch(() => props.empty, renderChart)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="analytics-chart-wrap" :aria-label="ariaLabel">
    <div ref="chartElement" class="analytics-chart" :aria-hidden="empty" />
    <div v-if="empty" class="analytics-chart-empty">
      <strong>暂无可绘制数据</strong>
      <span>{{ emptyText }}</span>
    </div>
  </div>
</template>
