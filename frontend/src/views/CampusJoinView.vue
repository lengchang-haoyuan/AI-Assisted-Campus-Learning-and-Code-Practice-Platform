<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getCampusMe, redeemInvitation } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import type { MembershipResponse } from '@/types/campus'

const router = useRouter()
const authStore = useAuthStore()
const membership = ref<MembershipResponse | null>(null)
const token = ref('')
const loading = ref(true)
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

onMounted(async () => {
  try {
    membership.value = (await getCampusMe()).membership
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '校园身份加载失败')
  } finally {
    loading.value = false
  }
})

async function redeem(): Promise<void> {
  if (submitting.value || token.value.trim().length < 32) return
  submitting.value = true
  errorMessage.value = null
  try {
    await redeemInvitation(token.value.trim())
    authStore.logout()
    await router.replace({ name: 'login', query: { notice: '校园身份已加入，请重新登录' } })
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '邀请兑换失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page-shell campus-page">
    <header class="page-header"><div><h1>校园身份</h1><p>校园资格独立于普通账号，仅接受管理员核验的定向邀请。</p></div></header>
    <div v-if="loading" class="campus-state">正在加载身份信息…</div>
    <div v-else-if="errorMessage" class="inline-alert is-error" role="alert">{{ errorMessage }}</div>
    <section v-else-if="membership" class="campus-card">
      <span class="campus-kicker">当前资格</span>
      <h2>{{ membership.role === 'administrator' ? '校园管理员' : membership.role === 'teacher' ? '教师' : '学生' }}</h2>
      <p>校园身份编号：#{{ membership.id }} · 状态：{{ membership.status }} · 身份版本 {{ membership.revision }}</p>
      <RouterLink v-if="membership.status === 'active'" class="secondary-command" to="/campus/classes">进入教学班</RouterLink>
      <RouterLink v-if="membership.role === 'administrator'" class="primary-command" to="/campus/admin/accounts">进入账号管理</RouterLink>
    </section>
    <section v-else class="campus-card">
      <span class="campus-kicker">加入试点</span><h2>兑换定向邀请</h2>
      <p>邀请必须与当前账号或邮箱匹配。成功加入后需重新登录。</p>
      <form class="campus-form" @submit.prevent="redeem">
        <label for="campus-token">邀请凭证</label>
        <input id="campus-token" v-model="token" type="password" autocomplete="off" minlength="32" maxlength="128" required />
        <button class="primary-command" type="submit" :disabled="submitting || token.trim().length < 32">{{ submitting ? '正在核验' : '核验并加入' }}</button>
      </form>
    </section>
  </div>
</template>
