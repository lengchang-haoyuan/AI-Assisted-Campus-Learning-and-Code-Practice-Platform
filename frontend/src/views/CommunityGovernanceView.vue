<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import {
  appealGovernanceAction,
  decideGovernanceCase,
  decidePublication,
  listGovernanceCases,
  listModerationPublications,
  listMyPublications,
} from '@/api/community'
import { useAuthStore } from '@/stores/auth'
import type { GovernanceCaseResponse, PublicationResponse } from '@/types/community'

const authStore = useAuthStore()
const publications = ref<PublicationResponse[]>([])
const moderationQueue = ref<PublicationResponse[]>([])
const cases = ref<GovernanceCaseResponse[]>([])
const loading = ref(true)
const actionLoading = ref(false)
const errorMessage = ref<string | null>(null)
const isAdministrator = ref(false)
const caseFilter = ref<'all' | 'pending'>('all')

const publicationStatusLabels: Record<PublicationResponse['status'], string> = {
  legacy_review_required: '历史作品待补审', pending_review: '等待审核', approved: '审核通过',
  returned: '已退回', withdrawn: '已撤回', taken_down: '已下架',
}
const caseStatusLabels: Record<GovernanceCaseResponse['status'], string> = {
  pending: '待处理', accepted: '已支持', rejected: '未支持',
}
const visibleCases = computed(() => caseFilter.value === 'pending'
  ? cases.value.filter((item) => item.status === 'pending')
  : cases.value)

function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}
function requestKey(prefix: string): string {
  return typeof crypto.randomUUID === 'function' ? crypto.randomUUID().replaceAll('-', '') : `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

async function loadData(): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const membership = (await getCampusMe()).membership
    isAdministrator.value = membership?.role === 'administrator' && membership.status === 'active'
    const [myResult, caseResult, queueResult] = await Promise.all([
      listMyPublications(), listGovernanceCases(),
      isAdministrator.value ? listModerationPublications() : Promise.resolve(null),
    ])
    publications.value = myResult.items
    cases.value = caseResult.items
    moderationQueue.value = queueResult?.items ?? []
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '治理进度加载失败')
  } finally { loading.value = false }
}

async function reviewPublication(item: PublicationResponse, decision: 'approve' | 'return'): Promise<void> {
  const title = decision === 'approve' ? '通过发布申请' : '退回发布申请'
  try {
    const { value } = await ElMessageBox.prompt('请填写审核理由（至少 3 个字符），作者会收到处理结果。', title, {
      confirmButtonText: decision === 'approve' ? '确认通过' : '确认退回', cancelButtonText: '取消',
      inputValidator: (text) => text.trim().length >= 3 || '请填写至少 3 个字符',
    })
    actionLoading.value = true
    await decidePublication(item.id, item.revision, decision, value.trim())
    ElMessage.success(decision === 'approve' ? '发布申请已通过' : '发布申请已退回')
    await loadData()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '审核失败，请刷新后重试'))
  } finally { actionLoading.value = false }
}

async function reviewCase(item: GovernanceCaseResponse, decision: 'accept' | 'reject'): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt('请填写处理理由（至少 3 个字符）。相关用户只会看到其有权获知的信息。', decision === 'accept' ? '支持该请求' : '不支持该请求', {
      confirmButtonText: '确认处理', cancelButtonText: '取消', inputValidator: (text) => text.trim().length >= 3 || '请填写至少 3 个字符',
    })
    actionLoading.value = true
    await decideGovernanceCase(item.id, item.revision, decision, value.trim())
    ElMessage.success('治理案件已处理')
    await loadData()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '案件处理失败，请刷新后重试'))
  } finally { actionLoading.value = false }
}

async function appealCase(item: GovernanceCaseResponse): Promise<void> {
  if (!item.resolved_action_id) return
  try {
    const { value } = await ElMessageBox.prompt('说明需要复核的事实或理由（至少 3 个字符）。', '提交复核申请', {
      confirmButtonText: '提交复核', cancelButtonText: '取消', inputValidator: (text) => text.trim().length >= 3 || '请填写至少 3 个字符',
    })
    actionLoading.value = true
    await appealGovernanceAction(item.resolved_action_id, value.trim(), requestKey('appeal'))
    ElMessage.success('复核申请已提交')
    await loadData()
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '复核申请失败'))
  } finally { actionLoading.value = false }
}

onMounted(() => void loadData())
</script>

<template>
  <div class="page-shell governance-page">
    <header class="page-header governance-header">
      <div><p class="page-kicker">Campus Governance</p><h1>社区治理进度</h1><p>查看发布审核、举报处理和与你有关的复核结果。举报者身份及内部备注不会向无关用户公开。</p></div>
      <RouterLink class="secondary-command" to="/community">返回社区</RouterLink>
    </header>

    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadData">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading" aria-label="治理数据加载中"><span v-for="index in 3" :key="index" /></div>

    <template v-else>
      <section v-if="isAdministrator" class="governance-section">
        <div class="panel-title-row"><div><p class="page-kicker">Administrator</p><h2>待审发布申请</h2></div><span>{{ moderationQueue.length }} 项</span></div>
        <div v-if="moderationQueue.length" class="governance-list">
          <article v-for="item in moderationQueue" :key="item.id" class="governance-card">
            <div><span class="status-chip">{{ publicationStatusLabels[item.status] }}</span><h3>{{ item.pending_version?.name ?? item.public_version?.name ?? `发布记录 #${item.id}` }}</h3><p>作者账号 #{{ item.owner_user_id }} · 版本 {{ item.pending_version_number ?? item.public_version_number }}</p><p>{{ item.pending_version?.description || '未填写项目说明' }}</p></div>
            <dl class="governance-facts"><div><dt>类型</dt><dd>{{ item.kind === 'practice_template' ? '实践项目模板' : '校园作品' }}</dd></div><div><dt>署名</dt><dd>{{ item.pending_version?.attribution || item.public_version?.attribution || '未填写' }}</dd></div><div><dt>来源/许可</dt><dd>{{ item.pending_version?.source_license_statement || item.public_version?.source_license_statement || '未填写' }}</dd></div><div><dt>AI 声明</dt><dd>{{ item.pending_version?.ai_assistance_statement || item.public_version?.ai_assistance_statement || '未填写' }}</dd></div></dl>
            <div class="governance-card__actions"><button class="secondary-command compact-command" type="button" :disabled="actionLoading" @click="reviewPublication(item, 'return')">退回</button><button class="primary-command compact-command" type="button" :disabled="actionLoading" @click="reviewPublication(item, 'approve')">通过</button></div>
          </article>
        </div>
        <p v-else class="teaching-note">当前没有待审发布申请。</p>
      </section>

      <section class="governance-section">
        <div class="panel-title-row"><div><p class="page-kicker">Publications</p><h2>我的发布</h2></div><span>{{ publications.length }} 项</span></div>
        <div v-if="publications.length" class="governance-list">
          <article v-for="item in publications" :key="item.id" class="governance-card is-compact">
            <div><span class="status-chip">{{ publicationStatusLabels[item.status] }}</span><h3>{{ item.pending_version?.name ?? item.public_version?.name ?? `发布记录 #${item.id}` }}</h3><p>公开版本 {{ item.public_version_number ?? '—' }} · 待审版本 {{ item.pending_version_number ?? '—' }} · 更新于 {{ formatDate(item.reviewed_at ?? item.submitted_at) }}</p></div>
            <RouterLink v-if="item.project_id" class="secondary-command compact-command" :to="`/projects/${item.project_id}`">查看项目</RouterLink>
          </article>
        </div><p v-else class="teaching-note">你还没有提交社区发布申请。</p>
      </section>

      <section class="governance-section">
        <div class="panel-title-row"><div><p class="page-kicker">Reports & Appeals</p><h2>{{ isAdministrator ? '举报与复核案件' : '与我相关的案件' }}</h2></div><label class="submission-filter"><input v-model="caseFilter" type="checkbox" true-value="pending" false-value="all" /> 只看待处理</label></div>
        <div v-if="visibleCases.length" class="governance-list">
          <article v-for="item in visibleCases" :key="item.id" class="governance-card is-compact">
            <div><div class="tag-row"><span class="status-chip">{{ item.case_type === 'report' ? '举报' : '复核' }}</span><span class="tech-tag">{{ caseStatusLabels[item.status] }}</span></div><h3>{{ item.target_excerpt }}</h3><p>目标：{{ item.target_type }} · 提交于 {{ formatDate(item.created_at) }}</p><p v-if="item.reason">申请理由：{{ item.reason }}</p><p v-else-if="item.opened_by_user_id === null">出于举报人隐私，仅展示处理所需结果。</p><p v-if="item.resolution_reason">处理结果：{{ item.resolution_reason }}</p></div>
            <div class="governance-card__actions">
              <template v-if="isAdministrator && item.status === 'pending'"><button class="secondary-command compact-command" type="button" :disabled="actionLoading" @click="reviewCase(item, 'reject')">不支持</button><button class="primary-command compact-command" type="button" :disabled="actionLoading" @click="reviewCase(item, 'accept')">支持并执行</button></template>
              <button v-else-if="item.status === 'accepted' && item.resolved_action_id && item.target_owner_user_id === authStore.currentUser?.id" class="secondary-command compact-command" type="button" :disabled="actionLoading" @click="appealCase(item)">申请复核</button>
            </div>
          </article>
        </div><p v-else class="teaching-note">当前没有符合条件的案件。</p>
      </section>
    </template>
  </div>
</template>
