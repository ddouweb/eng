<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ score: number; max?: number }>(), { max: 100 })

const pct = computed(() => Math.max(0, Math.min(1, props.score / props.max)))

// 按总分着色：>=80 绿 / >=60 蓝 / >=40 橙 / 否则灰
const color = computed(() => {
  const p = pct.value
  if (p >= 0.8) return '#18a058'
  if (p >= 0.6) return '#2080f0'
  if (p >= 0.4) return '#f0a020'
  return '#909399'
})

const R = 52
const C = 2 * Math.PI * R
const dash = computed(() => `${pct.value * C} ${C}`)
</script>

<template>
  <div class="ring">
    <svg viewBox="0 0 120 120">
      <circle cx="60" cy="60" :r="R" fill="none" stroke="#eef0f3" stroke-width="11" />
      <circle
        cx="60"
        cy="60"
        :r="R"
        fill="none"
        :stroke="color"
        stroke-width="11"
        stroke-linecap="round"
        :stroke-dasharray="dash"
        transform="rotate(-90 60 60)"
      />
    </svg>
    <div class="center">
      <div class="score">{{ score }}</div>
      <div class="max">/ {{ max }}</div>
    </div>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  width: 140px;
  height: 140px;
}
svg {
  width: 100%;
  height: 100%;
}
.center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}
.max {
  font-size: 13px;
  color: #999;
}
</style>
