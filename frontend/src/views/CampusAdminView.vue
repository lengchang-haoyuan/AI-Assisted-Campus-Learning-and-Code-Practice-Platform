<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createInvitation,
  getAccounts,
  getAudits,
  getInvitations,
  issuePasswordReset,
  revokeInvitation,
  updateAccount,
} from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import type { AccountResponse, AuditResponse, InvitationResponse } from '@/types/campus'

type AccountAction = 'disable' | 'enable' | 'suspend' | 'activate' | 'revoke' | 'student' | 'teacher' | 'administrator'
interface OperationState { action: AccountAction; reason: string }

const accounts = ref<AccountResponse[]>([])
const invitations = ref<InvitationResponse[]>([])
const audits = ref<AuditResponse[]>([])
const query = ref('')
const loading = ref(true)
const errorMessage = ref<string | null>(null)
const notice = ref<string | null>(null)
const oneTimeToken = ref<string | null>(null)
const operations = reactive<Record<number, OperationState>>({})
const invite = reactive({ target: '', role: 'student' as 'student' | 'teacher', hours: 72, reason: '' })

function operationState(account: AccountResponse): OperationState {
  operations[account.user_id] ??= { action: account.account_enabled ? 'disable' : 'enable', reason: '' }
  return operations[account.user_id]!
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const [accountPage, invitationPage, auditPage] = await Promise.all([
      getAccounts(query.value.trim()), getInvitations(), getAudits(),
    ])
    accounts.value = accountPage.items
    invitations.value = invitationPage.items
    audits.value = auditPage.items
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '账号管理数据加载失败')
  } finally {
    loading.value = false
  }
}

async function issueInvite(): Promise<void> {
  errorMessage.value = null
  notice.value = null
  oneTimeToken.value = null
  try {
    const numericTarget = /^\d+$/.test(invite.target.trim()) ? Number(invite.target.trim()) : null
    const result = await createInvitation({
      ...(numericTarget ? { target_user_id: numericTarget } : { target_email: invite.target.trim() }),
      role: invite.role,
      expires_in_hours: invite.hours,
      reason: invite.reason.trim(),
    })
    oneTimeToken.value = result.token
    notice.value = '邀请已创建。凭证仅显示本次，请通过已批准渠道交付。'
    invite.target = ''
    invite.reason = ''
    await load()
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '邀请创建失败')
  }
}

async function applyAccountOperation(account: AccountResponse): Promise<void> {
  const state = operationState(account)
  if (state.reason.trim().length < 3) {
    errorMessage.value = '管理操作必须填写至少 3 个字符的原因'
    return
  }
  if (!window.confirm(`确认对账号 ${account.username} 执行此操作？`)) return
  const input = state.action === 'disable' || state.action === 'enable'
    ? { reason: state.reason.trim(), expected_auth_version: account.auth_version, account_enabled: state.action === 'enable' }
    : state.action === 'suspend' || state.action === 'activate' || state.action === 'revoke'
      ? { reason: state.reason.trim(), expected_revision: account.membership?.revision, campus_status: state.action === 'activate' ? 'active' as const : state.action === 'suspend' ? 'suspended' as const : 'revoked' as const }
      : { reason: state.reason.trim(), expected_revision: account.membership?.revision, role: state.action }
  try {
    await updateAccount(account.user_id, input)
    notice.value = '账号状态已更新，目标账号的旧会话已撤销。'
    state.reason = ''
    await load()
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '账号更新失败')
  }
}

async function createReset(account: AccountResponse): Promise<void> {
  const reason = window.prompt(`请输入为 ${account.username} 签发重置凭证的原因`)
  if (!reason || reason.trim().length < 3) return
  if (!window.confirm('确认签发一次性密码重置凭证？旧的未使用凭证会失效。')) return
  try {
    const result = await issuePasswordReset(account.user_id, reason.trim())
    oneTimeToken.value = result.token
    notice.value = '密码重置凭证已签发，仅显示本次。'
    await load()
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '重置凭证签发失败')
  }
}

async function revoke(invitation: InvitationResponse): Promise<void> {
  const reason = window.prompt('请输入撤销邀请的原因')
  if (!reason || reason.trim().length < 3 || !window.confirm('确认撤销此邀请？')) return
  try {
    await revokeInvitation(invitation.id, reason.trim())
    notice.value = '邀请已撤销。'
    await load()
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '邀请撤销失败')
  }
}

async function copyToken(): Promise<void> {
  if (oneTimeToken.value) await navigator.clipboard.writeText(oneTimeToken.value)
}

onMounted(load)
</script>

<template>
  <div class="page-shell campus-page campus-admin-page">
    <header class="page-header"><div><span class="campus-kicker">P17 · 固定角色</span><h1>校园账号管理</h1><p>仅管理账号元数据、校园资格与一次性凭证，不读取私人项目、笔记、Context 或 AI 输入。</p></div></header>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert">{{ errorMessage }}</div>
    <div v-if="notice" class="inline-alert is-success" role="status">{{ notice }}</div>
    <section v-if="oneTimeToken" class="campus-token-panel" aria-live="polite">
      <strong>一次性凭证</strong><code>{{ oneTimeToken }}</code><button class="secondary-command" type="button" @click="copyToken">复制</button>
      <small>离开或刷新页面后不再显示。</small>
    </section>

    <section class="campus-card">
      <div class="panel-title-row"><div><h2>签发邀请</h2><p>管理员只能邀请学生或教师，目标必须是账号编号或核验邮箱。</p></div></div>
      <form class="campus-inline-form" @submit.prevent="issueInvite">
        <label>目标账号或邮箱<input v-model="invite.target" required maxlength="255" placeholder="账号编号或邮箱" /></label>
        <label>角色<select v-model="invite.role"><option value="student">学生</option><option value="teacher">教师</option></select></label>
        <label>有效小时<input v-model.number="invite.hours" type="number" min="1" max="72" required /></label>
        <label class="is-wide">核验原因<input v-model="invite.reason" minlength="3" maxlength="500" required /></label>
        <button class="primary-command" type="submit">创建邀请</button>
      </form>
    </section>

    <section class="campus-card">
      <div class="panel-title-row"><div><h2>账号</h2><p>共 {{ accounts.length }} 条当前结果；每次只执行一个有版本保护的操作。</p></div><form class="campus-search" @submit.prevent="load"><input v-model="query" maxlength="100" placeholder="用户名或邮箱" /><button class="secondary-command">查询</button></form></div>
      <div v-if="loading" class="campus-state">正在加载…</div>
      <div v-else-if="accounts.length === 0" class="campus-state">没有匹配账号</div>
      <article v-for="account in accounts" v-else :key="account.user_id" class="campus-account-row">
        <div><strong>{{ account.username }}</strong><span>{{ account.email }}</span><small>#{{ account.user_id }} · {{ account.account_enabled ? '账号启用' : '账号停用' }} · {{ account.membership ? `${account.membership.role} / ${account.membership.status}` : '无校园身份' }}</small></div>
        <select v-model="operationState(account).action">
          <option :value="account.account_enabled ? 'disable' : 'enable'">{{ account.account_enabled ? '停用账号' : '启用账号' }}</option>
          <template v-if="account.membership && account.membership.status !== 'revoked'"><option value="suspend">暂停校园资格</option><option value="activate">恢复校园资格</option><option value="revoke">撤销校园资格</option><option value="student">调整为学生</option><option value="teacher">调整为教师</option><option value="administrator">调整为管理员</option></template>
        </select>
        <input v-model="operationState(account).reason" maxlength="500" placeholder="操作原因" aria-label="操作原因" />
        <div class="campus-row-actions"><button class="danger-command" type="button" @click="applyAccountOperation(account)">确认执行</button><button class="secondary-command" type="button" @click="createReset(account)">重置凭证</button></div>
      </article>
    </section>

    <div class="campus-admin-grid">
      <section class="campus-card"><h2>最近邀请</h2><div v-if="invitations.length === 0" class="campus-state">暂无邀请</div><article v-for="item in invitations" :key="item.id" class="campus-log-row"><span>#{{ item.id }} · {{ item.target_email || `账号 ${item.target_user_id}` }}</span><small>{{ item.role }} · {{ item.status }}</small><button v-if="item.status === 'pending'" class="text-command" type="button" @click="revoke(item)">撤销</button></article></section>
      <section class="campus-card"><h2>账号审计</h2><div v-if="audits.length === 0" class="campus-state">暂无审计记录</div><article v-for="item in audits" :key="item.id" class="campus-log-row"><span>{{ item.action }} · {{ item.outcome }}</span><small>操作者 #{{ item.actor_user_id }} · 对象 {{ item.target_user_id ? `#${item.target_user_id}` : '—' }}</small><time>{{ new Date(item.occurred_at).toLocaleString('zh-CN') }}</time></article></section>
    </div>
  </div>
</template>
