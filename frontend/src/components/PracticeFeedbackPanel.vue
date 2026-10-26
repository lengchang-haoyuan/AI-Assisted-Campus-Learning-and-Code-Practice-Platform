<script setup lang="ts">
import type { PracticeAttempt, PracticeTemplate } from '@/types/practice'
defineProps<{ attempt: PracticeAttempt; template: PracticeTemplate; fake: boolean }>()
function time(value: string): string { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
</script>

<template>
  <section class="practice-evidence" aria-label="所选提交的五类证据">
    <header><h2>提交 {{ attempt.attempt_no }} 的审阅材料</h2><p>每一项保留自己的来源。本人结束仅记录审阅这份材料。</p></header>
    <section><h3>自我声明</h3><p>{{ attempt.feedback.self_statement.value === null ? '未提供自测声明' : attempt.feedback.self_statement.value ? '本人声明已完成自测' : '本人声明尚未完成自测' }}</p></section>
    <section><h3>输出值核对</h3><p>{{ attempt.feedback.submitted_output_match.matched ? '声明值与公开样例一致' : '声明值缺失或与公开样例不一致' }}。平台未运行代码。</p>
      <ul><li v-for="check in attempt.feedback.submitted_output_match.checks" :key="check.test_id">{{ check.test_id }}：{{ check.matched ? '声明值一致' : '声明值缺失或不一致' }}</li></ul>
    </section>
    <section><h3>AI 辅助建议 <span v-if="fake" class="practice-source">Fake 工程演示</span></h3>
      <template v-if="attempt.feedback.ai_static_review">
        <p>{{ attempt.feedback.ai_static_review.review.summary }}</p>
        <p class="muted-copy">来源：本次提交 · 请求 #{{ attempt.feedback.ai_static_review.ai_request_id }}。以下是模型建议，供自行核对。</p>
        <details v-for="item in attempt.feedback.ai_static_review.review.criteria" :key="item.criterion_id" :open="item.verdict !== 'pass'">
          <summary>{{ template.criteria.find(entry => entry.criterion_id === item.criterion_id)?.name ?? item.criterion_id }} · {{ item.verdict === 'fail' ? '建议核对' : item.verdict === 'unknown' ? '信息不足' : '暂无新增问题线索' }}</summary>
          <p>{{ item.reason }}</p><pre v-if="item.evidence_span" tabindex="0" aria-label="建议引用的代码">{{ item.evidence_span }}</pre>
          <p v-if="item.suggested_self_test"><strong>建议自测：</strong>{{ item.suggested_self_test }}</p>
          <p v-if="item.next_action"><strong>可选下一步：</strong>{{ item.next_action }}</p>
        </details>
      </template>
      <p v-else-if="attempt.feedback.review_error">本次建议未取得（{{ attempt.feedback.review_error.code }}）。可以恢复等待，也可以审阅现有提交后结束。</p>
      <p v-else>尚未请求或取得此提交的 AI 建议。你可以直接审阅自己的提交。</p>
    </section>
    <section><h3>本人确认</h3><p v-if="attempt.feedback.personal_confirmation">本人已审阅本次材料 · {{ time(attempt.feedback.personal_confirmation.confirmed_at) }}</p><p v-else>尚未确认审阅。</p></section>
    <section><h3>教师确认</h3><p>{{ attempt.feedback.teacher_confirmation === null ? '未提供正式教师确认' : '存在正式来源记录，请在教学模块核对' }}</p></section>
  </section>
</template>
