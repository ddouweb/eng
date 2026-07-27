<script setup lang="ts">
import { useRoute } from 'vue-router'
import { NCard } from 'naive-ui'

const route = useRoute()
</script>

<template>
  <NCard>
    <h2 style="margin-top: 0">{{ route.meta.icon }} {{ route.meta.title }}</h2>
    <p style="color: #999">🚧 该页面待迁移（批次进行中）。期间可继续用 Streamlit（:8501）版本。</p>
  </NCard>
</template>
