<script setup lang="ts">
export interface LiquidTabOption {
  value: string
  label: string
}

defineProps<{
  modelValue: string
  options: LiquidTabOption[]
  ariaLabel: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="liquid-tabs" role="tablist" :aria-label="ariaLabel">
    <button
      v-for="option in options"
      :key="option.value"
      class="liquid-tabs__item"
      :class="{ 'is-active': modelValue === option.value }"
      type="button"
      role="tab"
      :aria-selected="modelValue === option.value"
      @click="emit('update:modelValue', option.value)"
    >
      <span>{{ option.label }}</span>
    </button>
  </div>
</template>
