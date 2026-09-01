<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import lostFoundCover from '@/assets/projects/lost-found-cover.png'
import { getApiErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ username: '', email: '', password: '', confirmPassword: '' })
const errorMessage = ref<string | null>(null)
const fieldErrors = ref<Record<string, string>>({})

function validate(): boolean {
  const errors: Record<string, string> = {}
  const username = form.username.trim()
  const email = form.email.trim()
  if (!/^[A-Za-z0-9_]{3,50}$/.test(username)) {
    errors.username = '用户名需为 3–50 位字母、数字或下划线'
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) errors.email = '请输入有效邮箱'
  if (form.password.length < 8) errors.password = '密码至少需要 8 个字符'
  if (form.password !== form.confirmPassword) errors.confirmPassword = '两次输入的密码不一致'
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit(): Promise<void> {
  if (!validate() || authStore.loading) return
  errorMessage.value = null
  try {
    await authStore.register({
      username: form.username.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password,
    })
    await router.replace({
      name: 'login',
      query: { registered: '1', identifier: form.username.trim() },
    })
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '注册失败，请检查输入后重试')
  }
}
</script>

<template>
  <main class="auth-page is-register">
    <section class="auth-visual" aria-labelledby="register-product-title">
      <RouterLink class="app-brand auth-brand" to="/">ScholarHub</RouterLink>
      <div class="auth-visual__content">
        <h1 id="register-product-title">从第一个项目开始，建立自己的校园实践档案。</h1>
        <p>真实项目、清晰状态，以及下一步要做的事。</p>
      </div>
      <img :src="lostFoundCover" alt="校园地图与定位图钉插画" />
    </section>

    <section class="auth-form-panel" aria-labelledby="register-title">
      <div class="auth-form-wrap">
        <h2 id="register-title">创建账号</h2>
        <p>注册后即可创建并维护自己的学习项目。</p>

        <form class="auth-form" novalidate @submit.prevent="submit">
          <div v-if="errorMessage" class="inline-alert is-error" role="alert">
            {{ errorMessage }}
          </div>

          <label class="field">
            <span>用户名</span>
            <input v-model="form.username" autocomplete="username" maxlength="50" autofocus />
            <small v-if="fieldErrors.username" class="field-error">{{ fieldErrors.username }}</small>
          </label>

          <label class="field">
            <span>邮箱</span>
            <input v-model="form.email" type="email" autocomplete="email" maxlength="255" />
            <small v-if="fieldErrors.email" class="field-error">{{ fieldErrors.email }}</small>
          </label>

          <div class="form-grid">
            <label class="field">
              <span>密码</span>
              <input v-model="form.password" type="password" autocomplete="new-password" maxlength="128" />
              <small v-if="fieldErrors.password" class="field-error">{{ fieldErrors.password }}</small>
            </label>
            <label class="field">
              <span>确认密码</span>
              <input
                v-model="form.confirmPassword"
                type="password"
                autocomplete="new-password"
                maxlength="128"
              />
              <small v-if="fieldErrors.confirmPassword" class="field-error">
                {{ fieldErrors.confirmPassword }}
              </small>
            </label>
          </div>

          <button class="primary-command auth-submit" type="submit" :disabled="authStore.loading">
            {{ authStore.loading ? '正在创建…' : '创建账号' }}
          </button>
        </form>

        <p class="auth-switch">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
      </div>
    </section>
  </main>
</template>
