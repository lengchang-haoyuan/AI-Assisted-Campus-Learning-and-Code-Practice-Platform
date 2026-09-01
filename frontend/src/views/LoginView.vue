<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import featuredCover from '@/assets/projects/featured-cover.png'
import { getApiErrorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ identifier: '', password: '' })
const errorMessage = ref<string | null>(null)
const fieldErrors = ref<Record<string, string>>({})
const successMessage = ref<string | null>(null)

onMounted(() => {
  if (typeof route.query.identifier === 'string') form.identifier = route.query.identifier
  if (route.query.registered === '1') successMessage.value = '账号创建成功，请登录'
})

function safeRedirect(): string {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return redirect
  }
  return '/'
}

function validate(): boolean {
  const errors: Record<string, string> = {}
  if (form.identifier.trim().length < 3) errors.identifier = '请输入用户名或邮箱'
  if (!form.password) errors.password = '请输入密码'
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit(): Promise<void> {
  if (!validate() || authStore.loading) return
  errorMessage.value = null
  try {
    await authStore.login({ identifier: form.identifier.trim(), password: form.password })
    await router.replace(safeRedirect())
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '登录失败，请检查账号和密码')
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-visual" aria-labelledby="auth-product-title">
      <RouterLink class="app-brand auth-brand" to="/">ScholarHub</RouterLink>
      <div class="auth-visual__content">
        <h1 id="auth-product-title">把校园项目和每天的学习节奏放在同一张桌面上。</h1>
        <p>管理自己的代码实践，保留每一次清晰的进展。</p>
      </div>
      <img :src="featuredCover" alt="绿色文档检查项目插画" />
    </section>

    <section class="auth-form-panel" aria-labelledby="login-title">
      <div class="auth-form-wrap">
        <h2 id="login-title">欢迎回来</h2>
        <p>使用用户名或邮箱继续进入 ScholarHub。</p>

        <form class="auth-form" novalidate @submit.prevent="submit">
          <div v-if="successMessage" class="inline-alert is-success" role="status">
            {{ successMessage }}
          </div>
          <div v-if="errorMessage" class="inline-alert is-error" role="alert">
            {{ errorMessage }}
          </div>

          <label class="field">
            <span>用户名或邮箱</span>
            <input
              v-model="form.identifier"
              name="identifier"
              autocomplete="username"
              maxlength="255"
              autofocus
            />
            <small v-if="fieldErrors.identifier" class="field-error">
              {{ fieldErrors.identifier }}
            </small>
          </label>

          <label class="field">
            <span>密码</span>
            <input
              v-model="form.password"
              type="password"
              name="password"
              autocomplete="current-password"
              maxlength="128"
            />
            <small v-if="fieldErrors.password" class="field-error">{{ fieldErrors.password }}</small>
          </label>

          <button class="primary-command auth-submit" type="submit" :disabled="authStore.loading">
            {{ authStore.loading ? '正在登录…' : '登录' }}
          </button>
        </form>

        <p class="auth-switch">还没有账号？<RouterLink to="/register">创建账号</RouterLink></p>
      </div>
    </section>
  </main>
</template>
