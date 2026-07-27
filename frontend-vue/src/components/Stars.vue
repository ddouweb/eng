<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ count: number; max?: number }>(), { max: 5 })

const cells = computed(() =>
  Array.from({ length: props.max }, (_, i) => i < props.count),
)
</script>

<template>
  <span class="stars">
    <span v-for="(on, i) in cells" :key="i" :class="on ? 'on' : 'off'">★</span>
  </span>
</template>

<style scoped>
.stars {
  font-size: 22px;
  letter-spacing: 2px;
}
.on {
  color: #f0a020;
}
.off {
  color: #ddd;
}
</style>
