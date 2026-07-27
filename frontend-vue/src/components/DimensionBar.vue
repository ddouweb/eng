<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  icon: string
  score: number
  max: number
  color: string
}>()

const pct = computed(() =>
  props.max > 0 ? Math.max(0, Math.min(100, (props.score / props.max) * 100)) : 0,
)
</script>

<template>
  <div class="dim">
    <div class="dim-head">
      <span class="dim-label">{{ icon }} {{ label }}</span>
      <span class="dim-score">{{ score }} / {{ max }}</span>
    </div>
    <div class="bar">
      <div class="fill" :style="{ width: pct + '%', background: color }" />
    </div>
  </div>
</template>

<style scoped>
.dim {
  margin-bottom: 12px;
}
.dim-head {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  margin-bottom: 5px;
}
.dim-label {
  color: #444;
}
.dim-score {
  color: #888;
  font-variant-numeric: tabular-nums;
}
.bar {
  height: 10px;
  background: #eef0f3;
  border-radius: 5px;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.4s ease;
}
</style>
