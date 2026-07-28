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
  NTag,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import type { EChartsOption } from 'echarts'

import { api } from '@/api/client'
import type { DailyTrend, StatsOverview, StatsProfile } from '@/api/types'
import { MASTERY_META, MASTERY_ORDER, type MasteryLevel } from '@/constants/mastery'
import { BADGES } from '@/constants/badges'
import EChart from '@/components/EChart.vue'

// 忠实迁移自 frontend/pages/5_🏆_排行榜.py（单人模式后为自我纵向进步趋势）。
const message = useMessage()
const loading = ref(true)
const profile = ref<StatsProfile | null>(null)
const overview = ref<StatsOverview | null>(null)
const trendDays = ref(7)
const trendDaily = ref<DailyTrend[]>([])
const trendLoading = ref(false)
const trendError = ref('')
const heatDaily = ref<DailyTrend[]>([])
const heatLoading = ref(false)
const heatError = ref('')
const overviewError = ref('')

// ECharts 不吃 CSS 变量，故在此固化掌握度四色十六进制（与 styles/tokens.css 一致）。
const MASTERY_HEX: Record<MasteryLevel, string> = {
  unlearned: '#9CA3AF',
  learning: '#F97316',
  familiar: '#3B82F6',
  permanent: '#22C55E',
}

const DAY_OPTIONS: SelectOption[] = [
  { label: '最近 7 天', value: 7 },
  { label: '最近 14 天', value: 14 },
  { label: '最近 30 天', value: 30 },
]

// ── 日期工具（本地时区，规避 UTC 偏移导致错位一天）──
function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// XP 段位进度（满级 100，否则 clamp(progress,0,1)*100）。
const xpPercent = computed(() => {
  const lv = profile.value?.level
  if (!lv) return 0
  if (lv.next_level_min_xp == null) return 100
  return Math.max(0, Math.min(1, lv.progress)) * 100
})

const xpText = computed(() => {
  const p = profile.value
  if (!p) return ''
  const lv = p.level
  if (lv.next_level_min_xp == null) return `${lv.level_icon} ${lv.level_name}（满级）`
  return `${lv.level_icon} ${lv.level_name} → ${lv.next_level_name}`
})

// ── 图表 option ──
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

// ── 数据加载 ──
async function loadProfile() {
  const r = await api.getStatsProfile()
  if (r.code === 200) profile.value = r.data
  else message.error(`坚持数据加载失败：${r.message}`)
}

async function loadOverview() {
  const r = await api.getStatsOverview()
  if (r.code === 200) {
    overview.value = r.data
    overviewError.value = ''
  } else {
    overview.value = null
    overviewError.value = r.message || '数据加载失败'
  }
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
  await Promise.all([loadProfile(), loadOverview(), loadTrend(), loadHeatmap()])
  loading.value = false
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🏆 我的进步趋势</h2>
    <p class="caption">
      单人模式 · 追踪你自己的坚持与进步（连续打卡 · 练习趋势 · 掌握分布 · 个人最佳）。
    </p>

    <!-- 顶部：坚持指标 -->
    <template v-if="profile">
      <div class="cards">
        <NCard size="small">
          <NStatistic label="🔥 连续学习" :value="`${profile.current_streak} 天`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="🏆 最长记录" :value="`${profile.longest_streak} 天`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="⭐ 累计 XP" :value="profile.total_xp" />
        </NCard>
        <NCard size="small">
          <NStatistic
            :label="`${profile.level.level_icon} 段位`"
            :value="profile.level.level_name"
          />
        </NCard>
      </div>

      <!-- XP 进度条（到下一段位） -->
      <NCard size="small">
        <div class="xp-text">{{ xpText }}</div>
        <NProgress
          type="line"
          :percentage="xpPercent"
          :show-indicator="false"
          :height="14"
          :border-radius="6"
        />
      </NCard>

      <!-- 徽章 -->
      <NCard size="small" title="🎖️ 徽章">
        <NSpace v-if="profile.badges.length" :size="8" wrap>
          <NTag
            v-for="b in profile.badges"
            :key="b"
            type="success"
            size="medium"
            round
            :bordered="false"
          >
            {{ BADGES[b]?.icon ?? '🏅' }} {{ BADGES[b]?.name ?? b }}
          </NTag>
        </NSpace>
        <p v-else class="hint" style="margin: 0">
          还没有徽章——连续学习 7 天、累计 100 XP 即可解锁第一个！
        </p>
      </NCard>
    </template>

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

    <!-- 掌握分布 + 个人最佳 -->
    <template v-if="overview">
      <h3 class="section">个人最佳</h3>
      <div class="cards">
        <NCard size="small">
          <NStatistic label="累计答题" :value="overview.total_questions" />
        </NCard>
        <NCard size="small">
          <NStatistic label="总正确率" :value="`${overview.accuracy}%`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="已掌握" :value="overview.mastered_count" />
        </NCard>
      </div>

      <h3 class="section">掌握分布</h3>
      <NCard v-if="masteryDistOption" size="small">
        <EChart :option="masteryDistOption" height="280px" />
      </NCard>
      <NEmpty v-else description="暂无掌握度数据" />
    </template>
    <NResult
      v-else-if="overviewError"
      status="error"
      title="数据加载失败"
      :description="overviewError"
    >
      <template #footer>
        <NButton @click="loadOverview">重试</NButton>
      </template>
    </NResult>
  </NSpin>
</template>

<style scoped>
.caption {
  color: #666;
  margin-top: -8px;
  font-size: 13px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.section {
  margin: 22px 0 10px;
  font-size: 17px;
  font-weight: 600;
}
.xp-text {
  margin-bottom: 8px;
  font-size: 14px;
  color: #555;
}
.hint {
  color: #6B7280;
  font-size: 13px;
  margin: 8px 0 0;
  text-align: center;
}
</style>
