<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NEmpty,
  NProgress,
  NResult,
  NSelect,
  NSpace,
  NSpin,
  NStatistic,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import type { EChartsOption } from 'echarts'

import { api } from '@/api/client'
import type { DailyTrend, MasteryDist, ReviewDue, StatsOverview, Unit } from '@/api/types'
import { MASTERY_META, MASTERY_ORDER, type MasteryLevel } from '@/constants/mastery'
import EChart from '@/components/EChart.vue'

// 忠实迁移自 frontend/pages/4_📊_统计.py。
const message = useMessage()
const loading = ref(true)
const overview = ref<StatsOverview | null>(null)
const reviewDue = ref<ReviewDue | null>(null)
const units = ref<Unit[]>([])

// getStatsUnit 返回 unknown，这里固化其结构（与 StatsOverview 同构，但单 Unit 维度）。
interface UnitStats {
  total_words: number
  mastered_count: number
  mastery_rate: number
  mastery_distribution: MasteryDist
}
const unitStats = ref<Record<number, UnitStats>>({})

// ECharts 不吃 CSS 变量，故在此固化掌握度四色十六进制（与 styles/tokens.css 一致）。
const MASTERY_HEX: Record<MasteryLevel, string> = {
  unlearned: '#9CA3AF',
  learning: '#F97316',
  familiar: '#3B82F6',
  permanent: '#22C55E',
}

const trendDays = ref(7)
const trendDaily = ref<DailyTrend[]>([])
const trendLoading = ref(false)
const trendError = ref('')
const heatDaily = ref<DailyTrend[]>([])
const heatLoading = ref(false)
const heatError = ref('')
const overviewError = ref('')

const DAY_OPTIONS: SelectOption[] = [
  { label: '最近 7 天', value: 7 },
  { label: '最近 14 天', value: 14 },
  { label: '最近 30 天', value: 30 },
  { label: '最近 84 天', value: 84 },
]

// ── 日期工具（本地时区，规避 UTC 偏移导致错位一天）──
function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// ── 图表 option ──
const masteryDistOption = computed<EChartsOption | null>(() => {
  const dist = overview.value?.mastery_distribution
  if (!dist) return null
  const cats = MASTERY_ORDER.map((lv) => `${MASTERY_META[lv].emoji} ${MASTERY_META[lv].label}`)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 48, right: 24, top: 24, bottom: 32 },
    xAxis: { type: 'category', data: cats, axisTick: { show: false } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        barWidth: '55%',
        data: MASTERY_ORDER.map((lv) => ({
          value: dist[lv],
          itemStyle: { color: MASTERY_HEX[lv] },
        })),
      },
    ],
  }
})

const trendOption = computed<EChartsOption | null>(() => {
  const daily = trendDaily.value
  if (!daily.length) return null
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['练习量', '正确量'], top: 4 },
    grid: { left: 48, right: 24, top: 40, bottom: 32 },
    xAxis: { type: 'category', data: daily.map((d) => d.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '练习量',
        type: 'bar',
        data: daily.map((d) => d.total),
        itemStyle: { color: '#3B82F6' },
      },
      {
        name: '正确量',
        type: 'line',
        data: daily.map((d) => d.correct),
        smooth: true,
        itemStyle: { color: '#18a058' },
        lineStyle: { color: '#18a058' },
      },
    ],
  }
})

// 12 周贡献热力图：getStatsTrend(84) 的 daily → 日历热力图。
// daily 中每天的 total 作为当日练习量；缺失日期按 0 填充；色域 #ebedf0→#2da44e（GitHub 风）。
const heatmapOption = computed<EChartsOption | null>(() => {
  const daily = heatDaily.value
  if (!daily.length) return null
  const cnt = new Map<string, number>(daily.map((d) => [d.date, d.total]))
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const data: Array<[string, number]> = []
  let maxCount = 0
  for (let i = 83; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    const ds = formatDate(d)
    const c = cnt.get(ds) ?? 0
    data.push([ds, c])
    if (c > maxCount) maxCount = c
  }
  const start = new Date(today)
  start.setDate(start.getDate() - 83)
  return {
    tooltip: {
      formatter: (p: unknown) => {
        const v = (p as { value: [string, number] }).value
        return `${v[0]}：${v[1]} 题`
      },
    },
    visualMap: {
      type: 'continuous',
      min: 0,
      max: Math.max(10, maxCount),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#ebedf0', '#2da44e'] },
      show: true,
    },
    calendar: {
      top: 30,
      left: 30,
      right: 30,
      bottom: 20,
      cellSize: ['auto', 14],
      range: [formatDate(start), formatDate(today)],
      itemStyle: { borderWidth: 2, borderColor: '#fff', color: '#ebedf0' },
      splitLine: { show: false },
      yearLabel: { show: false },
      dayLabel: { firstDay: 1, nameMap: 'ZH', fontSize: 11 },
      monthLabel: { nameMap: 'ZH', fontSize: 11 },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', data }],
  }
})

// ── 数据加载 ──
async function loadOverview() {
  const r = await api.getStatsOverview()
  if (r.code === 200) {
    overview.value = r.data
    overviewError.value = ''
  } else {
    overview.value = null
    overviewError.value = r.message || '概览加载失败'
    message.error(`概览加载失败：${r.message}`)
  }
}

async function loadReviewDue() {
  const r = await api.getReviewDue()
  if (r.code === 200) reviewDue.value = r.data
  else message.error(`复习压力加载失败：${r.message}`)
}

async function loadUnitsAndStats() {
  const r = await api.listAllUnits()
  if (r.code !== 200) {
    message.error(`Unit 列表加载失败：${r.message}`)
    return
  }
  units.value = r.data.items
  const entries = await Promise.all(
    units.value.map(async (u): Promise<[number, UnitStats | null]> => {
      const sr = await api.getStatsUnit(u.id)
      if (sr.code !== 200) return [u.id, null]
      return [u.id, sr.data as UnitStats]
    }),
  )
  const map: Record<number, UnitStats> = {}
  for (const [id, stats] of entries) {
    if (stats) map[id] = stats
  }
  unitStats.value = map
}

async function loadTrend() {
  trendLoading.value = true
  const r = await api.getStatsTrend(trendDays.value)
  trendLoading.value = false
  if (r.code === 200) {
    trendDaily.value = r.data.daily
    trendError.value = ''
  } else {
    trendDaily.value = []
    trendError.value = r.message || '趋势加载失败'
  }
}

async function loadHeatmap() {
  heatLoading.value = true
  const r = await api.getStatsTrend(84)
  heatLoading.value = false
  if (r.code === 200) {
    heatDaily.value = r.data.daily
    heatError.value = ''
  } else {
    heatDaily.value = []
    heatError.value = r.message || '热力图加载失败'
  }
}

function onTrendDaysChange(v: string | number) {
  trendDays.value = Number(v)
  void loadTrend()
}

onMounted(async () => {
  loading.value = true
  await Promise.all([
    loadOverview(),
    loadReviewDue(),
    loadUnitsAndStats(),
    loadTrend(),
    loadHeatmap(),
  ])
  loading.value = false
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">📊 学习统计</h2>

    <!-- 全局概览 -->
    <template v-if="overview">
      <div class="cards">
        <NCard size="small">
          <NStatistic label="总单词数" :value="overview.total_words" />
        </NCard>
        <NCard size="small">
          <NStatistic label="已掌握" :value="overview.mastered_count" />
        </NCard>
        <NCard size="small">
          <NStatistic label="练习次数" :value="overview.practice_session_count" />
        </NCard>
        <NCard size="small">
          <NStatistic label="连续学习" :value="`${overview.streak_days} 天`" />
        </NCard>
      </div>
      <div class="cards">
        <NCard size="small">
          <NStatistic label="掌握率" :value="`${overview.mastery_rate}%`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="正确率" :value="`${overview.accuracy}%`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="总答题数" :value="overview.total_questions" />
        </NCard>
      </div>
      <!-- SRS 到期复习压力 -->
      <div v-if="reviewDue" class="cards">
        <NCard size="small">
          <NStatistic label="🔁 今日到期" :value="reviewDue.due_today" />
        </NCard>
        <NCard size="small">
          <NStatistic label="⚠️ 已逾期" :value="reviewDue.overdue" />
        </NCard>
      </div>
      <NCard v-if="overview.total_words > 0" size="small">
        <NProgress
          type="line"
          :percentage="overview.mastery_rate"
          :show-indicator="false"
          :height="14"
          :border-radius="6"
        />
      </NCard>
    </template>

    <!-- 掌握分布 -->
    <h3 class="section">掌握分布</h3>
    <NCard v-if="masteryDistOption" size="small">
      <EChart :option="masteryDistOption" height="280px" />
    </NCard>
    <NResult
      v-else-if="overviewError"
      status="error"
      title="掌握度数据加载失败"
      :description="overviewError"
    >
      <template #footer>
        <NButton @click="loadOverview">重试</NButton>
      </template>
    </NResult>
    <NEmpty v-else description="暂无掌握度数据" />

    <!-- 按 Unit 统计 -->
    <h3 class="section">按 Unit 统计</h3>
    <NEmpty v-if="!units.length && !loading" description="还没有 Unit" />
    <NSpace v-else vertical :size="12">
      <NCard v-for="u in units" :key="u.id" size="small">
        <div class="unit-head">
          <span class="unit-title">{{ u.title }}</span>
          <span v-if="unitStats[u.id]" class="unit-rate">
            掌握率 {{ unitStats[u.id].mastery_rate }}%
          </span>
        </div>
        <NProgress
          v-if="unitStats[u.id]"
          type="line"
          :percentage="unitStats[u.id].mastery_rate"
          :height="10"
          :show-indicator="false"
          style="margin: 8px 0 12px"
        />
        <div v-if="unitStats[u.id]" class="cards no-mb">
          <NStatistic
            v-for="lv in MASTERY_ORDER"
            :key="lv"
            :label="`${MASTERY_META[lv].emoji} ${MASTERY_META[lv].label}`"
            :value="unitStats[u.id].mastery_distribution[lv]"
          />
        </div>
        <NEmpty v-else size="small" description="暂无统计" />
      </NCard>
    </NSpace>

    <!-- 练习趋势 -->
    <h3 class="section">练习趋势</h3>
    <NSpace align="center" style="margin-bottom: 12px">
      <span>时间范围</span>
      <NSelect
        :value="trendDays"
        :options="DAY_OPTIONS"
        style="width: 160px"
        @update:value="onTrendDaysChange"
      />
    </NSpace>
    <NCard v-if="trendOption" size="small">
      <NSpin :show="trendLoading">
        <EChart :option="trendOption" height="300px" />
      </NSpin>
    </NCard>
    <NResult
      v-else-if="trendError"
      status="error"
      title="趋势加载失败"
      :description="trendError"
    >
      <template #footer>
        <NButton :loading="trendLoading" @click="loadTrend">重试</NButton>
      </template>
    </NResult>
    <NEmpty v-else description="暂无练习记录" />

    <!-- 贡献热力图（最近 12 周） -->
    <h3 class="section">贡献热力图（最近 12 周）</h3>
    <NCard v-if="heatmapOption" size="small">
      <NSpin :show="heatLoading">
        <EChart :option="heatmapOption" height="220px" />
        <p class="hint">色块越绿＝当天练习量越大；空白＝当天未练习。</p>
      </NSpin>
    </NCard>
    <NResult
      v-else-if="heatError"
      status="error"
      title="热力图加载失败"
      :description="heatError"
    >
      <template #footer>
        <NButton :loading="heatLoading" @click="loadHeatmap">重试</NButton>
      </template>
    </NResult>
    <NEmpty v-else description="暂无练习记录，无法生成热力图" />
  </NSpin>
</template>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.cards.no-mb {
  margin-bottom: 0;
}
.section {
  margin: 22px 0 10px;
  font-size: 17px;
  font-weight: 600;
}
.unit-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.unit-title {
  font-weight: 600;
  font-size: 15px;
}
.unit-rate {
  color: #18a058;
  font-size: 13px;
}
.hint {
  color: #6B7280;
  font-size: 13px;
  margin: 8px 0 0;
  text-align: center;
}
</style>
