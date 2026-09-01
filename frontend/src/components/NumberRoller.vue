<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  value: number | string
}>()

const characters = computed(() => String(props.value).split(''))

function isDigit(character: string): boolean {
  return /^\d$/.test(character)
}
</script>

<template>
  <span class="number-roller" :aria-label="String(value)">
    <template v-for="(character, index) in characters" :key="`${index}-${character}`">
      <span v-if="isDigit(character)" class="number-roller__digit" aria-hidden="true">
        <span
          class="number-roller__track"
          :style="{ transform: `translateY(-${Number(character) * 10}%)` }"
        >
          <span v-for="digit in 10" :key="digit">{{ digit - 1 }}</span>
        </span>
      </span>
      <span v-else class="number-roller__symbol" aria-hidden="true">{{ character }}</span>
    </template>
  </span>
</template>
