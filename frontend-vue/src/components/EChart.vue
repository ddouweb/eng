<script lang="ts">
// 模块顶层：一次性注册本应用所有图表用到的 ECharts 模块（幂等，可重复注册）。
// 放在非 setup 的 <script> 块中，确保在组件实例化前（模块导入时）即完成注册。
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, HeatmapChart, LineChart, PieChart } from 'echarts/charts'
import {
  CalendarComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  HeatmapChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CalendarComponent,
  TitleComponent,
])
</script>

<script setup lang="ts">
// vue-echarts 薄封装：把 option / height 透传给 VChart。
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

withDefaults(defineProps<{ option: EChartsOption; height?: string }>(), {
  height: '320px',
})
</script>

<template>
  <VChart :option="option" autoresize :style="{ height, width: '100%' }" />
</template>
