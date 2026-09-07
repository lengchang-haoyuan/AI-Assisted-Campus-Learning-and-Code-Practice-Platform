<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { changePassword, logoutAll } from '@/api/auth'
import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { MembershipResponse } from '@/types/campus'

const authStore = useAuthStore()
const router = useRouter()
const membership = ref<MembershipResponse | null>(null)
const securityForm = reactive({ current: '', next: '', confirmation: '' })
const submitting = ref(false)
const errorMessage = ref<string | null>(null)
const createdAt = computed(() => {
  const value = authStore.currentUser?.created_at
  if (!value) return '未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long' }).format(date)
})
const userInitial = computed(() => authStore.currentUser?.username.slice(0, 1).toUpperCase() || 'S')

onMounted(async () => {
  try { membership.value = (await getCampusMe()).membership } catch { membership.value = null }
})

async function updatePassword(): Promise<void> {
  if (submitting.value) return
  if (securityForm.next.length < 8 || securityForm.next !== securityForm.confirmation) {
    errorMessage.value = '新密码至少 8 位，且两次输入必须一致'
    return
  }
  submitting.value = true
  errorMessage.value = null
  try {
    await changePassword(securityForm.current, securityForm.next)
    authStore.logout()
    await router.replace({ name: 'login', query: { notice: '密码已修改，请重新登录' } })
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '密码修改失败')
  } finally { submitting.value = false }
}

async function revokeSessions(): Promise<void> {
  if (!window.confirm('确认撤销当前账号的全部登录会话？')) return
  try {
    await logoutAll()
    authStore.logout()
    await router.replace({ name: 'login', query: { notice: '全部会话已撤销，请重新登录' } })
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '会话撤销失败')
  }
}
</script>

<template>
  <div class="page-shell profile-page">
    <header class="page-header">
      <div><h1>个人资料</h1><p>查看当前登录账号的基础信息。</p></div>
    </header>

    <section v-if="authStore.currentUser" class="profile-board">
      <div class="profile-identity">
        <span class="avatar is-large" aria-hidden="true">{{ userInitial }}</span>
        <div>
          <h2>{{ authStore.currentUser.username }}</h2>
          <p>{{ authStore.currentUser.bio || '暂未填写个人简介。' }}</p>
        </div>
      </div>
      <dl class="profile-facts">
        <div><dt>邮箱</dt><dd>{{ authStore.currentUser.email }}</dd></div>
        <div><dt>账号状态</dt><dd>{{ authStore.currentUser.is_active ? '正常' : '已停用' }}</dd></div>
        <div><dt>加入时间</dt><dd>{{ createdAt }}</dd></div>
        <div><dt>用户编号</dt><dd>{{ authStore.currentUser.id }}</dd></div>
      </dl>
    </section>
    <div v-else class="inline-alert is-error" role="alert">当前用户信息不可用，请重新登录。</div>

    <section v-if="authStore.currentUser" class="profile-security-grid">
      <div class="campus-card">
        <span class="campus-kicker">校园资格</span>
        <h2>{{ membership ? (membership.role === 'administrator' ? '校园管理员' : membership.role === 'teacher' ? '教师' : '学生') : '尚未加入校园试点' }}</h2>
        <p>{{ membership ? `状态 ${membership.status} · 身份版本 ${membership.revision}` : '普通账号和私人数据保持可用，校园范围需定向邀请。' }}</p>
        <RouterLink v-if="membership?.role === 'administrator' && membership.status === 'active'" class="primary-command" to="/campus/admin/accounts">管理校园账号</RouterLink>
        <RouterLink v-else-if="!membership" class="secondary-command" to="/campus/join">兑换邀请</RouterLink>
      </div>
      <div class="campus-card">
        <span class="campus-kicker">账号安全</span><h2>修改密码</h2>
        <div v-if="errorMessage" class="inline-alert is-error" role="alert">{{ errorMessage }}</div>
        <form class="campus-form" @submit.prevent="updatePassword">
          <label for="current-password">当前密码</label><input id="current-password" v-model="securityForm.current" type="password" autocomplete="current-password" required maxlength="128" />
          <label for="next-password">新密码</label><input id="next-password" v-model="securityForm.next" type="password" autocomplete="new-password" required minlength="8" maxlength="128" />
          <label for="confirm-password">确认新密码</label><input id="confirm-password" v-model="securityForm.confirmation" type="password" autocomplete="new-password" required minlength="8" maxlength="128" />
          <div class="campus-form-actions"><button class="primary-command" type="submit" :disabled="submitting">{{ submitting ? '正在修改' : '修改并重新登录' }}</button><button class="danger-command" type="button" @click="revokeSessions">撤销全部会话</button></div>
        </form>
      </div>
    </section>

  </div>
</template>
