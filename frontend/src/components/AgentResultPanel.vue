<script setup lang="ts">
import { ElMessage } from 'element-plus'

import type { AgentRecordResponse } from '@/types/ai'

const props = defineProps<{ record: AgentRecordResponse | null }>()

const statusLabels: Record<AgentRecordResponse['status'], string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

function formatTime(value: string | null): string {
  if (!value) return '尚未结束'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatLatency(value: number | null): string {
  return value === null ? '未统计' : `${(value / 1000).toFixed(1)} 秒`
}

async function copyText(value: string, successMessage: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success(successMessage)
  } catch {
    ElMessage.error('复制失败，请选择文本后手动复制')
  }
}

function copyResult(): void {
  if (!props.record?.result) return
  void copyText(JSON.stringify(props.record.result, null, 2), '结果已复制')
}

function copyPrompt(): void {
  const result = props.record?.result
  if (result?.result_type !== 'prompt') return
  void copyText(result.generated_prompt, '开发 Prompt 已复制')
}
</script>

<template>
  <section class="agent-result-panel" aria-labelledby="agent-result-title">
    <div v-if="!record" class="agent-result-empty">
      <strong id="agent-result-title">AI 结果</strong>
      <p>运行需求分析或开发 Prompt 后，结构化结果会显示在这里。</p>
    </div>

    <template v-else>
      <header class="agent-result-heading">
        <div>
          <span>请求 #{{ record.request_id }} · Context v{{ record.context_version }}</span>
          <h2 id="agent-result-title">{{ record.agent_type === 'project_analysis' ? '需求分析结果' : record.agent_type === 'prompt' ? '开发 Prompt 结果' : '项目审查结果' }}</h2>
        </div>
        <div class="agent-result-actions">
          <span class="status-chip" :data-status="record.status">{{ statusLabels[record.status] }}</span>
          <button v-if="record.result" class="secondary-command" type="button" @click="copyResult">复制结果</button>
        </div>
      </header>

      <dl class="agent-result-facts">
        <div><dt>Provider / 模型</dt><dd>{{ record.provider }} / {{ record.model }}</dd></div>
        <div><dt>发起时间</dt><dd>{{ formatTime(record.requested_at) }}</dd></div>
        <div><dt>完成时间</dt><dd>{{ formatTime(record.finished_at) }}</dd></div>
        <div><dt>耗时 / Tokens</dt><dd>{{ formatLatency(record.usage.latency_ms) }} / {{ record.usage.prompt_tokens === null || record.usage.completion_tokens === null ? '未统计' : record.usage.prompt_tokens + record.usage.completion_tokens }}</dd></div>
      </dl>

      <div v-if="record.error" class="inline-alert is-error" role="alert">
        <strong>{{ record.error.message }}</strong>
        <span>错误代码：{{ record.error.code }}。请先确认已有结果，再决定是否重新调用。</span>
      </div>

      <div v-if="record.status === 'pending' || record.status === 'running'" class="agent-running-state" role="status">
        <strong>模型调用仍在处理</strong>
        <p>当前接口为同步调用；离开页面或浏览器中断请求不代表服务端任务已经取消。</p>
      </div>

      <div v-if="record.result?.result_type === 'project_analysis'" class="agent-result-content">
        <p class="agent-result-summary">{{ record.result.summary }}</p>

        <section>
          <h3>需求拆解</h3>
          <article v-for="item in record.result.requirements_breakdown" :key="item.title" class="agent-result-card">
            <h4>{{ item.title }}</h4>
            <p>{{ item.description }}</p>
            <strong>验收标准</strong>
            <ul><li v-for="criterion in item.acceptance_criteria" :key="criterion">{{ criterion }}</li></ul>
          </article>
        </section>

        <section>
          <h3>开发步骤</h3>
          <ol class="agent-step-list">
            <li v-for="step in record.result.development_steps" :key="step.order">
              <strong>{{ step.order }}. {{ step.title }}</strong>
              <p>{{ step.action }}</p>
              <small>验证：{{ step.verification }}</small>
            </li>
          </ol>
        </section>

        <div class="agent-result-columns">
          <section>
            <h3>技术难点</h3>
            <article v-for="item in record.result.technical_challenges" :key="item.title" class="agent-result-card">
              <h4>{{ item.title }}</h4>
              <p>{{ item.reason }}</p>
              <small>建议：{{ item.mitigation }}</small>
            </article>
          </section>
          <section>
            <h3>技术建议</h3>
            <article v-for="item in record.result.technology_recommendations" :key="`${item.category}-${item.choice}`" class="agent-result-card">
              <small>{{ item.category }}</small>
              <h4>{{ item.choice }}</h4>
              <p>{{ item.reason }}</p>
              <span v-if="item.alternatives.length">备选：{{ item.alternatives.join('、') }}</span>
            </article>
          </section>
        </div>

        <section>
          <h3>知识点</h3>
          <div class="tag-row"><span v-for="item in record.result.knowledge_points" :key="item" class="tech-tag">{{ item }}</span></div>
        </section>
      </div>

      <div v-else-if="record.result?.result_type === 'prompt'" class="agent-result-content">
        <section class="agent-prompt-output">
          <div class="panel-title-row">
            <div><small>生成标题</small><h3>{{ record.result.title }}</h3></div>
            <button class="primary-command" type="button" @click="copyPrompt">复制开发 Prompt</button>
          </div>
          <pre>{{ record.result.generated_prompt }}</pre>
        </section>
        <div class="agent-result-columns">
          <section>
            <h3>验收标准</h3>
            <ul><li v-for="item in record.result.acceptance_criteria" :key="item">{{ item }}</li></ul>
          </section>
          <section>
            <h3>风险提示</h3>
            <p v-if="!record.result.risk_notes.length" class="muted-copy">模型未返回额外风险提示。</p>
            <ul v-else><li v-for="item in record.result.risk_notes" :key="item">{{ item }}</li></ul>
          </section>
        </div>
      </div>

      <div v-else-if="record.result?.result_type === 'project_review'" class="agent-result-content">
        <p class="agent-result-summary">{{ record.result.completion_summary }}</p>
        <section><h3>下一步</h3><ol class="agent-step-list"><li v-for="item in record.result.next_steps" :key="item.priority"><strong>{{ item.priority }}. {{ item.action }}</strong><small>验证：{{ item.verification }}</small></li></ol></section>
        <section><h3>问题</h3><article v-for="item in record.result.issues" :key="item.title" class="agent-result-card"><h4>{{ item.title }}</h4><p>{{ item.description }}</p><small>建议：{{ item.recommendation }}</small></article></section>
      </div>

      <p v-else-if="record.status === 'completed'" class="agent-result-empty">请求已完成，但没有可展示的结构化结果。</p>
    </template>
  </section>
</template>
