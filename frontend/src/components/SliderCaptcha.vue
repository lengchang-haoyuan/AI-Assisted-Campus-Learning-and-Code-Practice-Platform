<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { createSliderChallenge, verifySlider } from '@/api/auth'
import { getApiErrorMessage } from '@/api/errors'

const props = defineProps<{ disabled?: boolean }>()
const token = defineModel<string | null>({ required: true })
const track = ref<HTMLDivElement | null>(null)
const progress = ref(0)
const travel = ref(0)
const state = ref<'loading' | 'ready' | 'verifying' | 'verified' | 'error'>('loading')
const errorMessage = ref('')
const dragging = ref(false)
let challengeId: string | null = null
let pointerId: number | null = null
let startX = 0
let controller: AbortController | null = null
let expiryTimer: ReturnType<typeof setTimeout> | undefined
let resizeObserver: ResizeObserver | undefined

const available = computed(() => state.value === 'ready' && !props.disabled)
const label = computed(() => {
  if (state.value === 'loading') return '正在准备验证'
  if (state.value === 'verifying') return '正在验证'
  if (state.value === 'verified') return '验证通过'
  if (state.value === 'error') return '请刷新后重新验证'
  return progress.value >= 98 ? '松开完成验证' : '向右拖动滑块完成验证'
})

function expireAfter(seconds: number): void {
  clearTimeout(expiryTimer)
  expiryTimer = setTimeout(() => {
    token.value = null
    challengeId = null
    progress.value = 0
    dragging.value = false
    pointerId = null
    state.value = 'error'
    errorMessage.value = '验证已过期，请刷新后重试'
  }, seconds * 1000)
}

async function reset(): Promise<void> {
  controller?.abort()
  const requestController = new AbortController()
  controller = requestController
  clearTimeout(expiryTimer)
  token.value = null
  challengeId = null
  progress.value = 0
  pointerId = null
  dragging.value = false
  errorMessage.value = ''
  state.value = 'loading'
  try {
    const challenge = await createSliderChallenge(requestController.signal)
    if (requestController.signal.aborted) return
    challengeId = challenge.challenge_id
    state.value = 'ready'
    expireAfter(challenge.expires_in)
  } catch (error: unknown) {
    if (requestController.signal.aborted) return
    state.value = 'error'
    errorMessage.value = getApiErrorMessage(error, '验证加载失败，请刷新重试')
  }
}

async function finish(): Promise<void> {
  if (!available.value || !challengeId) return
  if (progress.value < 98) {
    progress.value = 0
    return
  }
  progress.value = 100
  state.value = 'verifying'
  clearTimeout(expiryTimer)
  const requestController = new AbortController()
  controller = requestController
  try {
    const result = await verifySlider(challengeId, 100, requestController.signal)
    if (requestController.signal.aborted) return
    token.value = result.slider_token
    state.value = 'verified'
    expireAfter(result.expires_in)
  } catch (error: unknown) {
    if (requestController.signal.aborted) return
    token.value = null
    state.value = 'error'
    progress.value = 0
    errorMessage.value = getApiErrorMessage(error, '验证失败，请刷新后重试')
  }
}

function pointerDown(event: PointerEvent): void {
  if (!available.value || !event.isPrimary || event.button !== 0) return
  if (!(event.currentTarget instanceof HTMLElement)) return
  event.preventDefault()
  event.currentTarget.focus()
  event.currentTarget.setPointerCapture(event.pointerId)
  pointerId = event.pointerId
  startX = event.clientX
  progress.value = 0
  dragging.value = true
}

function pointerMove(event: PointerEvent): void {
  if (!available.value || pointerId !== event.pointerId || !dragging.value) return
  progress.value = Math.max(0, Math.min(100, ((event.clientX - startX) / Math.max(1, travel.value)) * 100))
}

function pointerUp(event: PointerEvent): void {
  if (pointerId !== event.pointerId) return
  dragging.value = false
  pointerId = null
  void finish()
}

function cancelDrag(): void {
  dragging.value = false
  pointerId = null
  if (state.value === 'ready') progress.value = 0
}

function keyDown(event: KeyboardEvent): void {
  if (!available.value) return
  if (!['ArrowRight', 'ArrowLeft', 'Home', 'End', 'Enter', ' '].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'ArrowRight') progress.value = Math.min(100, progress.value + 5)
  if (event.key === 'ArrowLeft') progress.value = Math.max(0, progress.value - 5)
  if (event.key === 'Home') progress.value = 0
  if (event.key === 'End') progress.value = 100
  if (event.key === 'Enter' || event.key === ' ') void finish()
}

onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    if (entry) travel.value = Math.max(0, entry.contentRect.width - 54)
    if (dragging.value) cancelDrag()
  })
  if (track.value) resizeObserver.observe(track.value)
  void reset()
})

onBeforeUnmount(() => {
  controller?.abort()
  clearTimeout(expiryTimer)
  resizeObserver?.disconnect()
})

defineExpose({ reset })
</script>

<template>
  <div class="slider-captcha" :class="[`is-${state}`, { 'is-dragging': dragging }]">
    <div class="slider-captcha__heading">
      <span id="slider-title">滑块验证</span>
      <button
        class="slider-captcha__refresh"
        type="button"
        :disabled="disabled || state === 'loading' || state === 'verifying'"
        @click="reset"
      >{{ state === 'verified' ? '重新验证' : '刷新' }}</button>
    </div>
    <div ref="track" class="slider-captcha__track" :aria-busy="state === 'loading' || state === 'verifying'">
      <span class="slider-captcha__fill" :style="{ transform: `scaleX(${progress / 100})` }" />
      <span class="slider-captcha__label" role="status" aria-live="polite">{{ label }}</span>
      <button
        class="slider-captcha__thumb"
        type="button"
        role="slider"
        aria-labelledby="slider-title"
        aria-describedby="slider-instructions"
        :aria-valuemin="0"
        :aria-valuemax="100"
        :aria-valuenow="Math.round(progress)"
        :aria-valuetext="label"
        :aria-disabled="!available"
        :tabindex="available ? 0 : -1"
        :style="{ transform: `translateX(${travel * progress / 100}px)` }"
        @pointerdown="pointerDown"
        @pointermove="pointerMove"
        @pointerup="pointerUp"
        @pointercancel="cancelDrag"
        @lostpointercapture="cancelDrag"
        @keydown="keyDown"
      ><span :class="state === 'verified' ? 'slider-check' : 'slider-arrow'" aria-hidden="true" /></button>
    </div>
    <span id="slider-instructions" class="sr-only">向右拖动到底；也可以用方向键或 End 调整滑块，再按 Enter 完成验证。</span>
    <p v-if="errorMessage" class="slider-captcha__error" role="alert">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
.slider-captcha { min-width: 0; }
.slider-captcha__heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 9px; font-size: 13px; font-weight: 700; }
.slider-captcha__refresh { min-height: 24px; border: 0; padding: 0 2px; color: var(--blue); background: transparent; cursor: pointer; font-size: 12px; }
.slider-captcha__track { position: relative; height: 54px; border-radius: 6px; background: #eef3f2; box-shadow: inset 0 0 0 1px #d8e2df; overflow: hidden; user-select: none; }
.slider-captcha__fill { position: absolute; inset: 0; background: #bfe9d8; transform-origin: left; transition: transform 260ms ease, background-color 200ms; }
.slider-captcha__label { position: absolute; inset: 0; display: grid; place-items: center; padding: 0 52px; font-size: 12px; color: #405c51; white-space: nowrap; pointer-events: none; }
.slider-captcha__thumb { position: absolute; left: 5px; top: 5px; width: 44px; height: 44px; border: 0; border-radius: 5px; background: #fff; color: var(--mint-strong); box-shadow: 0 2px 6px rgb(23 75 60 / 14%); cursor: grab; touch-action: none; display: grid; place-items: center; transition: transform 260ms ease, border-radius 220ms, background-color 220ms; }
.slider-captcha__thumb:focus-visible { outline-offset: -3px; }
.slider-captcha__thumb[aria-disabled="true"] { cursor: default; }
.slider-arrow { width: 17px; height: 2px; background: currentColor; position: relative; }
.slider-arrow::after { content: ''; width: 8px; height: 8px; border-top: 2px solid currentColor; border-right: 2px solid currentColor; position: absolute; right: 0; top: -3px; transform: rotate(45deg); }
.slider-check { width: 9px; height: 16px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: translateY(-2px) rotate(45deg); }
.is-dragging .slider-captcha__thumb { cursor: grabbing; border-radius: 14px 6px 6px 14px; }
.is-dragging .slider-captcha__thumb, .is-dragging .slider-captcha__fill { transition: none; }
.is-verified .slider-captcha__thumb { background: var(--mint-strong); color: #fff; border-radius: 50%; }
.is-verified .slider-captcha__label { color: #175c46; font-weight: 700; }
.slider-captcha__error { margin: 8px 0 0; color: var(--danger); font-size: 12px; line-height: 1.5; }
.is-error .slider-captcha__track { box-shadow: inset 0 0 0 1px #ce8d91; }
@media (prefers-reduced-motion: reduce) {
  .slider-captcha__fill, .slider-captcha__thumb { transition: background-color 100ms; }
}
</style>
