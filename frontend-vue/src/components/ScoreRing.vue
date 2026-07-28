<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ score: number; max?: number }>(), { max: 100 })

const pct = computed(() => Math.max(0, Math.min(1, props.score / props.max)))

// 按总分着色：>=80 成功绿 / >=60 信息蓝 / >=40 警示橙 / 否则未学习灰。
// 颜色走 styles/tokens.css 语义 token，主题覆写与全站规范统一。
// 注意：SVG presentation 属性(stroke="...")不解析 CSS var()，必须经 CSS stroke 属性绑定。
const strokeColor = computed(() => {
  const p = pct.value
  if (p >= 0.8) return 'var(--success, #18a058)'
  if (p >= 0.6) return 'var(--info, #2080f0)'
  if (p >= 0.4) return 'var(--warning, #f0a020)'
  return 'var(--mastery-unlearned, #9ca3af)'
})

const R = 52
const C = 2 * Math.PI * R
const dash = computed(() => `${pct.value * C} ${C}`)
</script>

<template>
  <div class="ring">
    <svg viewBox="0 0 120 120">
      <circle
        cx="60"
        cy="60"
        :r="R"
        fill="none"
        :style="{ stroke: 'var(--track-bg, #eef0f3)' }"
        stroke-width="11"
      />
      <circle
        cx="60"
        cy="60"
        :r="R"
        fill="none"
        :style="{ stroke: strokeColor }"
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
  color: var(--text-primary, #1f2937);
}
.max {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}
</style>
