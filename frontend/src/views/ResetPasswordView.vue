<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { resetPassword } from '@/api/auth'
import { getApiErrorMessage } from '@/api/errors'

const route = useRoute()
const router = useRouter()
const form = reactive({ token: typeof route.query.token === 'string' ? route.query.token : '', password: '', confirmation: '' })
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function submit(): Promise<void> {
  if (submitting.value) return
  if (form.password.length < 8 || form.password !== form.confirmation) {
    errorMessage.value = '新密码至少 8 位，且两次输入必须一致'
    return
  }
  submitting.value = true
  errorMessage.value = null
  try {
    await resetPassword(form.token.trim(), form.password)
    await router.replace({ name: 'login', query: { notice: '密码已重置，请使用新密码登录' } })
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '密码重置失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-simple-page">
    <section class="auth-simple-card">
      <RouterLink class="app-brand" to="/">ScholarHub</RouterLink>
      <div><span class="campus-kicker">账号安全</span><h1>重置密码</h1><p>输入管理员核验后交付的一次性凭证。凭证使用后立即失效。</p></div>
      <div v-if="errorMessage" class="inline-alert is-error" role="alert">{{ errorMessage }}</div>
      <form class="campus-form" @submit.prevent="submit">
        <label for="reset-token">重置凭证</label><input id="reset-token" v-model="form.token" type="password" autocomplete="off" minlength="32" maxlength="128" required />
        <label for="reset-password">新密码</label><input id="reset-password" v-model="form.password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required />
        <label for="reset-confirmation">确认新密码</label><input id="reset-confirmation" v-model="form.confirmation" type="password" autocomplete="new-password" minlength="8" maxlength="128" required />
        <button class="primary-command" type="submit" :disabled="submitting">{{ submitting ? '正在重置' : '确认重置' }}</button>
      </form>
      <RouterLink to="/login">返回登录</RouterLink>
    </section>
  </main>
</template>
