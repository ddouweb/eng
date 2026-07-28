<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ count: number; max?: number }>(), { max: 5 })

const cells = computed(() =>
  Array.from({ length: props.max }, (_, i) => i < props.count),
)
</script>

<template>
  <span class="stars">
    <!-- 亮灭用字形区分（实心 ★ vs 空心 ☆），颜色仅作辅助：色盲也可辨识 -->
    <span
      v-for="(on, i) in cells"
      :key="i"
      class="star"
      :class="on ? 'on' : 'off'"
      :aria-label="on ? '已获得' : '未获得'"
      >{{ on ? '★' : '☆' }}</span
    >
  </span>
</template>

<style scoped>
.stars {
  font-size: 22px;
  letter-spacing: 2px;
}
.star {
  /* 字形为主要区分线索，颜色为辅助；确保空心星轮廓可见 */
  line-height: 1;
}
.on {
  color: var(--warning, #f0a020);
}
.off {
  color: #c9cdd4; /* 空心星描边：保留足够可见度的中性灰 */
}
</style>
