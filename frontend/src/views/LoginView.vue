<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElInput } from 'element-plus'
import 'element-plus/theme-chalk/el-input.css'
import 'element-plus/theme-chalk/el-icon.css'

import featuredCover from '@/assets/projects/featured-cover.png'
import classroomCover from '@/assets/projects/classroom-cover.png'
import communityCover from '@/assets/projects/lost-found-cover.png'
import { getApiErrorMessage } from '@/api/errors'
import SliderCaptcha from '@/components/SliderCaptcha.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ identifier: '', password: '' })
const errorMessage = ref<string | null>(null)
const fieldErrors = ref<Record<string, string>>({})
const successMessage = ref<string | null>(null)
const sliderToken = ref<string | null>(null)
const showPassword = ref(false)
const captcha = ref<InstanceType<typeof SliderCaptcha> | null>(null)
const activeScene = ref(0)
const scenes = [
  { id: 'projects', label: '项目实践', image: featuredCover, alt: '绿色文档与放大镜插画', title: '把灵感，写成自己的作品。', caption: '每一个认真开始的小项目，都有成长的可能。' },
  { id: 'learning', label: '学习工作台', image: classroomCover, alt: '学习空间插画', title: '按自己的节奏，积累进步。', caption: '今天的一点专注，会成为明天的底气。' },
  { id: 'community', label: '校园代码社区', image: communityCover, alt: '校园地图与定位图钉插画', title: '好想法，值得和同学分享。', caption: '在校园里找到同行的人，一起探索更多可能。' },
]
const scene = computed(() => scenes[activeScene.value] ?? scenes[0]!)

async function changeScene(event: KeyboardEvent): Promise<void> {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'Home') activeScene.value = 0
  else if (event.key === 'End') activeScene.value = scenes.length - 1
  else activeScene.value = (activeScene.value + (event.key === 'ArrowRight' ? 1 : -1) + scenes.length) % scenes.length
  await nextTick()
  document.getElementById(`story-tab-${activeScene.value}`)?.focus()
}

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
  if (!sliderToken.value) errors.slider = '请先完成下方滑块验证'
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submit(): Promise<void> {
  if (authStore.loading || !validate() || !sliderToken.value) return
  errorMessage.value = null
  try {
    await authStore.login({
      identifier: form.identifier.trim(),
      password: form.password,
      slider_token: sliderToken.value,
    })
    await router.replace(safeRedirect())
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '登录失败，请检查账号和密码')
    void captcha.value?.reset()
  }
}
</script>

<template>
  <main class="login-page">
    <header class="login-header">
      <RouterLink class="app-brand" to="/">ScholarHub</RouterLink>
      <span>校园里的灵感，在这里生长。</span>
    </header>
    <div class="login-body">
      <section class="login-story" aria-labelledby="auth-product-title">
        <h1 id="auth-product-title">把想法写进代码，<br /><em>把成长留给自己。</em></h1>
        <p class="login-story__intro">从校园里的一个灵感开始，继续你的下一步。</p>
        <div class="story-tabs" role="tablist" aria-label="校园实践主题" @keydown="changeScene">
          <span class="story-tabs__indicator" :style="{ transform: `translateX(${activeScene * 100}%)` }" aria-hidden="true" />
          <button
            v-for="(item, index) in scenes"
            :id="`story-tab-${index}`"
            :key="item.id"
            type="button"
            role="tab"
            :aria-selected="activeScene === index"
            aria-controls="story-panel"
            :tabindex="activeScene === index ? 0 : -1"
            @click="activeScene = index"
          >{{ item.label }}</button>
        </div>
        <figure id="story-panel" class="story-panel" role="tabpanel" :aria-labelledby="`story-tab-${activeScene}`">
          <div class="story-art">
            <Transition name="scene">
              <img :key="scene.id" :src="scene.image" :alt="scene.alt" fetchpriority="high" />
            </Transition>
          </div>
          <figcaption>
            <strong>{{ scene.title }}</strong>
            <span>{{ scene.caption }}</span>
          </figcaption>
        </figure>
      </section>

      <section class="login-form-surface" aria-labelledby="login-title">
        <div class="login-greeting" aria-hidden="true"><span /></div>
        <h2 id="login-title">欢迎回来</h2>
        <p class="login-form-intro">登录 ScholarHub，接着上次的进度。</p>

        <form class="login-form" novalidate @submit.prevent="submit">
          <Transition name="feedback">
            <div v-if="successMessage && !errorMessage" class="inline-alert is-success" role="status">{{ successMessage }}</div>
            <div v-else-if="errorMessage" class="inline-alert is-error" role="alert">{{ errorMessage }}</div>
          </Transition>

          <div class="login-field">
            <label for="login-identifier">用户名或邮箱</label>
            <ElInput
              id="login-identifier"
              v-model="form.identifier"
              name="identifier"
              autocomplete="username"
              maxlength="255"
              placeholder="输入你的用户名或邮箱"
              :disabled="authStore.loading"
              :aria-invalid="Boolean(fieldErrors.identifier)"
              :aria-describedby="fieldErrors.identifier ? 'identifier-error' : undefined"
              autofocus
            />
            <small v-if="fieldErrors.identifier" id="identifier-error" class="field-error">
              {{ fieldErrors.identifier }}
            </small>
          </div>

          <div class="login-field">
            <label for="login-password">密码</label>
            <ElInput
              id="login-password"
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              autocomplete="current-password"
              maxlength="128"
              placeholder="输入你的密码"
              :disabled="authStore.loading"
              :aria-invalid="Boolean(fieldErrors.password)"
              :aria-describedby="fieldErrors.password ? 'password-error' : undefined"
            >
              <template #suffix>
                <button
                  class="login-password-toggle"
                  type="button"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                  :aria-pressed="showPassword"
                  :disabled="authStore.loading"
                  @click="showPassword = !showPassword"
                >{{ showPassword ? '隐藏' : '显示' }}</button>
              </template>
            </ElInput>
            <small v-if="fieldErrors.password" id="password-error" class="field-error">{{ fieldErrors.password }}</small>
          </div>

          <div>
            <SliderCaptcha ref="captcha" v-model="sliderToken" :disabled="authStore.loading" />
            <small v-if="fieldErrors.slider && !sliderToken" class="field-error" role="alert">{{ fieldErrors.slider }}</small>
          </div>

          <button class="login-submit" type="submit" :disabled="authStore.loading">
            <span v-if="authStore.loading" class="login-spinner" aria-hidden="true" />
            {{ authStore.loading ? '正在登录' : '登录' }}
            <span v-if="!authStore.loading" class="login-submit__arrow" aria-hidden="true" />
          </button>
        </form>

        <p class="login-switch">还没有账号？<RouterLink to="/register">创建账号</RouterLink></p>
        <div class="login-note"><span aria-hidden="true" />每一份好奇，都值得一个开始。</div>
      </section>
    </div>
    <footer class="login-footer"><span>ScholarHub · 学习与代码实践</span><span>保持好奇，持续创造。</span></footer>
  </main>
</template>

<style scoped>
.login-page { min-height: 100svh; background: #f6faf8; color: var(--ink); letter-spacing: 0; }
.login-header { max-width: 1320px; min-height: 90px; margin: 0 auto; padding: 24px 48px; display: flex; align-items: center; justify-content: space-between; gap: 20px; border-bottom: 1px solid #dde8e2; }
.login-header > span { color: #537064; font-size: 13px; }
.login-body { max-width: 1260px; min-height: calc(100svh - 158px); padding: 42px 48px 46px; margin: 0 auto; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(0, 0.88fr); gap: 92px; align-items: center; }
.login-story { min-width: 0; }
.login-story h1 { font-size: 38px; line-height: 1.5; font-weight: 750; margin: 0 0 14px; }
.login-story h1 em { font-style: normal; color: #19775f; }
.login-story__intro { color: #53685f; font-size: 14px; line-height: 1.8; margin: 0 0 26px; }
.story-tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); position: relative; padding: 4px; background: #e5efeb; border-radius: 7px; max-width: 430px; margin-bottom: 22px; isolation: isolate; }
.story-tabs__indicator { position: absolute; z-index: -1; top: 4px; bottom: 4px; left: 4px; width: calc((100% - 8px) / 3); background: #fff; border-radius: 5px; box-shadow: 0 2px 4px rgb(23 75 60 / 8%); transition: transform 380ms cubic-bezier(0.16, 1, 0.3, 1); }
.story-tabs button { border: 0; background: transparent; min-height: 36px; padding: 6px 8px; color: #53685f; font-size: 12px; cursor: pointer; border-radius: 5px; }
.story-tabs button[aria-selected="true"] { color: #175d47; font-weight: 700; }
.story-tabs button:hover { color: #17232f; }
.story-panel { margin: 0; }
.story-art { position: relative; width: 100%; max-width: 360px; aspect-ratio: 1; overflow: hidden; border-radius: 8px; background: #dcefe5; animation: artwork-arrive 650ms cubic-bezier(0.16, 1, 0.3, 1) both; }
.story-art img { position: absolute; width: 100%; height: 100%; object-fit: cover; transition: transform 500ms cubic-bezier(0.16, 1, 0.3, 1); }
.story-art:hover img { transform: scale(1.025); }
.story-panel figcaption { min-height: 78px; padding: 19px 0 0; display: flex; flex-direction: column; gap: 7px; }
.story-panel figcaption strong { font-size: 16px; font-weight: 700; }
.story-panel figcaption span { font-size: 12px; line-height: 1.7; color: #53685f; }
.login-form-surface { width: 100%; max-width: 420px; padding: 20px 0; justify-self: end; animation: form-arrive 500ms cubic-bezier(0.16, 1, 0.3, 1) both; }
.login-greeting { width: 44px; height: 44px; border-radius: 8px; margin-bottom: 20px; background: #e6efff; display: grid; place-items: center; color: var(--blue); }
.login-greeting span { display: block; width: 18px; height: 23px; border: 2px solid currentColor; border-radius: 3px; position: relative; }
.login-greeting span::after { content: ''; position: absolute; width: 4px; height: 2px; top: 9px; right: 2px; background: currentColor; }
.login-form-surface h2 { font-size: 30px; margin: 0 0 10px; }
.login-form-intro { color: #586a63; font-size: 14px; line-height: 1.8; margin-bottom: 26px; }
.login-form { display: grid; gap: 19px; }
.login-field { display: grid; gap: 9px; }
.login-field > label { font-size: 13px; font-weight: 700; }
.login-field :deep(.el-input) { --el-input-height: 50px; --el-input-border-radius: 6px; --el-input-border-color: #cfded6; --el-input-focus-border-color: #2867d8; --el-input-placeholder-color: #718179; --el-input-text-color: #17232f; }
.login-field :deep(.el-input__wrapper) { padding: 1px 14px; transition: box-shadow 180ms; }
.login-field :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #2867d8 inset, 0 0 0 3px rgb(40 103 216 / 10%); }
.login-field :deep(.el-input__inner) { caret-color: #2867d8; font-size: 14px; }
.login-password-toggle { border: 0; background: transparent; align-self: center; min-height: 32px; padding: 0 0 0 8px; line-height: 1.4; color: #2867d8; font-size: 12px; cursor: pointer; }
.login-form .field-error { display: block; margin-top: 3px; font-size: 12px; line-height: 1.5; }
.login-submit { display: flex; align-items: center; justify-content: center; gap: 12px; width: 100%; min-height: 50px; padding: 12px 22px; border: 0; border-radius: 6px; background: #2867d8; color: white; font-size: 15px; font-weight: 700; cursor: pointer; box-shadow: 0 6px 16px rgb(40 103 216 / 15%); transition: background-color 150ms, box-shadow 150ms; }
.login-submit:hover:not(:disabled) { background: #205abd; box-shadow: 0 9px 22px rgb(40 103 216 / 20%); }
.login-submit:active:not(:disabled) { background: #194da6; }
.login-submit__arrow { position: relative; width: 17px; height: 2px; background: currentColor; transition: transform 200ms; }
.login-submit__arrow::after { content: ''; width: 7px; height: 7px; border-top: 2px solid currentColor; border-right: 2px solid currentColor; position: absolute; right: 0; top: -2.5px; transform: rotate(45deg); }
.login-submit:hover .login-submit__arrow { transform: translateX(3px); }
.login-spinner { width: 16px; height: 16px; border: 2px solid rgb(255 255 255 / 40%); border-top-color: #fff; border-radius: 50%; animation: login-spin 700ms linear infinite; }
.login-switch { font-size: 13px; text-align: center; color: #53685f; margin: 22px 0 0; }
.login-switch a { color: #2867d8; font-weight: 700; margin-left: 8px; text-underline-offset: 4px; }
.login-switch a:hover { text-decoration: underline; }
.login-note { display: flex; justify-content: center; align-items: center; gap: 9px; padding-top: 22px; margin-top: 25px; border-top: 1px solid #dce7e1; color: #64756c; font-size: 12px; }
.login-note > span { width: 18px; height: 2px; background: #d58a4d; }
.login-footer { max-width: 1320px; min-height: 68px; margin: 0 auto; padding: 20px 48px; border-top: 1px solid #dde8e2; display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #5d7267; font-size: 12px; }
.scene-enter-active, .scene-leave-active { transition: opacity 250ms ease, transform 350ms ease !important; }
.scene-enter-from { opacity: 0; transform: translateX(24px) scale(1.04); }
.scene-leave-to { opacity: 0; transform: translateX(-20px); }
.feedback-enter-active, .feedback-leave-active { transition: opacity 160ms ease, transform 160ms ease; }
.feedback-enter-from, .feedback-leave-to { opacity: 0; transform: translateY(-5px); }
@keyframes artwork-arrive { from { clip-path: inset(0 0 14% 0 round 8px); opacity: 0.65; transform: translateY(12px); } to { clip-path: inset(0 round 8px); opacity: 1; transform: none; } }
@keyframes form-arrive { from { opacity: 0.6; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes login-spin { to { transform: rotate(360deg); } }
@media (max-width: 1100px) {
  .login-body { gap: 48px; padding-right: 36px; padding-left: 36px; }
  .login-story h1 { font-size: 31px; }
}
@media (max-width: 800px) {
  .login-header { min-height: 76px; padding: 20px 28px; }
  .login-header > span { font-size: 12px; }
  .login-body { max-width: 540px; min-height: calc(100svh - 136px); display: flex; flex-direction: column; gap: 34px; padding: 30px 28px; }
  .login-form-surface { order: 0; max-width: none; padding: 0; }
  .login-story { order: 1; width: 100%; padding-top: 30px; border-top: 1px solid #dce7e1; }
  .login-story h1 { font-size: 27px; }
  .login-greeting { display: none; }
  .login-note { margin-top: 20px; padding-top: 20px; }
  .login-footer { min-height: 60px; padding: 18px 28px; font-size: 11px; }
}
@media (max-width: 380px) {
  .login-header { padding: 20px; }
  .login-header > span { display: none; }
  .login-body { padding: 28px 20px; }
  .login-story h1 { font-size: 24px; }
  .login-footer { flex-wrap: wrap; padding: 18px 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .story-art, .login-form-surface { animation: none; }
  .story-art img, .story-tabs__indicator, .login-submit__arrow { transition: none; }
  .story-art:hover img { transform: none; }
  .scene-enter-active, .scene-leave-active, .feedback-enter-active, .feedback-leave-active { transition: opacity 100ms !important; }
  .scene-enter-from, .scene-leave-to, .feedback-enter-from, .feedback-leave-to { transform: none; }
}
</style>
