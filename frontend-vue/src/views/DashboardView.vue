<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NProgress,
  NResult,
  NSpace,
  NSpin,
  NStatistic,
  NTag,
  useMessage,
} from 'naive-ui'

import { api } from '@/api/client'
import type { ReviewDue, StatsProfile } from '@/api/types'
import { BADGES } from '@/constants/badges'

// 完整仪表盘（批次 5）：指标卡 / XP 进度 / 断签预警 / 回归引导 / 徽章 / 今日到期复习。
// 忠实迁移自 frontend/app.py 的首页仪表盘部分。
const message = useMessage()
const router = useRouter()

const profile = ref<StatsProfile | null>(null)
const reviewDue = ref<ReviewDue | null>(null)
const loading = ref(true)
// profile 加载错误文案；非 null 即进入错误态（NResult + 重试），与「真空态」严格区分。
const loadError = ref<string | null>(null)

// 解析 ISO 日期串（YYYY-MM-DD）为本地日 0 点 Date；非法返回 null。
// 直接 new Date('2026-07-24') 会被当 UTC 0 点，本地时区偏移可能错位一天。
function parseDate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

// a - b 的整天天数（按本地日 0 点对齐，规避夏令时漂移）。
function daysBetween(a: Date, b: Date): number {
  const aa = new Date(a.getFullYear(), a.getMonth(), a.getDate())
  const bb = new Date(b.getFullYear(), b.getMonth(), b.getDate())
  return Math.round((aa.getTime() - bb.getTime()) / 86400000)
}

const lastDate = computed<Date | null>(() => {
  const s = profile.value?.last_active_date
  if (!s) return null
  return parseDate(s)
})

// 今天距上次活跃的天数（今天 − last_active_date）；无日期返回 null。
const gapDays = computed<number | null>(() => {
  if (!lastDate.value) return null
  return daysBetween(new Date(), lastDate.value)
})

// 断签预警：last_active_date < 今天 且 current_streak>0
const showStreakWarning = computed(() => {
  const g = gapDays.value
  return g !== null && g > 0 && (profile.value?.current_streak ?? 0) > 0
})

// 回归引导：(今天 − last_active_date).days >= 3
const showWelcomeBack = computed(() => {
  const g = gapDays.value
  return g !== null && g >= 3
})

// XP 进度百分比：满级 100，否则 clamp(progress, 0, 1) * 100。
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
  if (lv.next_level_min_xp == null) {
    return `${lv.level_icon} ${lv.level_name}（满级）　·　累计 ${p.total_xp} XP`
  }
  return `${lv.level_icon} ${lv.level_name} → ${lv.next_level_name}　·　累计 ${p.total_xp} XP`
})

async function load() {
  loading.value = true
  loadError.value = null
  // profile 是主数据：失败 → 进入错误态（可重试）。reviewDue 是辅助数据：失败仅 toast，不阻塞整页。
  const [profileResp, reviewResp] = await Promise.all([
    api.getStatsProfile(),
    api.getReviewDue(),
  ])
  if (profileResp.code === 200) {
    profile.value = profileResp.data
  } else {
    // 接口失败 ≠ 空数据：记下文案交给 NResult 渲染，并保留 profile=null 以走错误分支而非空态。
    profile.value = null
    loadError.value = profileResp.message || `加载失败（HTTP ${profileResp.code}）`
  }
  if (reviewResp.code === 200) {
    reviewDue.value = reviewResp.data
  } else {
    message.error(`复习数据加载失败：${reviewResp.message}`)
  }
  loading.value = false
}

function goPractice() {
  router.push('/practice')
}

function goPlans() {
  router.push('/plans')
}

onMounted(load)
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">📚 Family English Coach</h2>
    <p class="subtitle">词库练习 → 掌握追踪 → 每日复习</p>

    <!-- 错误态：profile 接口失败（非 200 / 抛错）。给重试入口，而不是整页空白或误报「暂无数据」。 -->
    <NResult
      v-if="loadError"
      status="error"
      title="坚持数据加载失败"
      :description="loadError"
    >
      <template #footer>
        <NButton type="primary" @click="load">🔄 重试</NButton>
      </template>
    </NResult>

    <!-- 空态：接口成功但确实无数据（profile 为空）。与错误态严格区分。-->
    <!-- 加载中（loading=true）时不渲染，避免 spinner 下方闪现空态。 -->
    <NEmpty
      v-else-if="!loading && !profile"
      description="暂无学习数据，去练习开启你的第一天吧～"
    >
      <template #extra>
        <NButton type="primary" @click="goPractice">🎯 去练习</NButton>
      </template>
    </NEmpty>

    <!-- 成功态 -->
    <div v-else-if="profile" class="dashboard">
      <!-- 顶部 CTA：核心行动入口置顶，不埋在最后一个区块。-->
      <NCard size="small" class="cta-banner">
        <div class="cta-row">
          <div class="cta-text">
            <template v-if="reviewDue && reviewDue.due_today > 0">
              🔁 今天有 <b>{{ reviewDue.due_today }}</b> 个单词到期复习<span
                v-if="reviewDue.overdue"
                >（{{ reviewDue.overdue }} 个已逾期）</span
              >
            </template>
            <template v-else-if="reviewDue">
              ✅ 今天没有到期单词，可以学点新词或休息一下
            </template>
            <template v-else>🎯 开始今天的练习，保持连胜节奏</template>
          </div>
          <NSpace :size="8" wrap>
            <NButton type="primary" @click="goPractice">🎯 去练习</NButton>
            <NButton @click="goPlans">📅 学习计划</NButton>
          </NSpace>
        </div>
      </NCard>

      <!-- 4 张指标卡 -->
      <div class="cards">
        <NCard size="small">
          <NStatistic label="🔥 连续学习" :value="`${profile.current_streak} 天`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="🛡️ 断签冻结" :value="`${profile.freeze_balance} 个`" />
        </NCard>
        <NCard size="small">
          <NStatistic label="🏆 最长记录" :value="`${profile.longest_streak} 天`" />
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

      <!-- 断签预警 -->
      <NAlert v-if="showStreakWarning" type="warning">
        ⚠️ 你已连续 <b>{{ profile.current_streak }}</b> 天，今天还没练习——别让记录断在今晚！(可用 🛡️ 冻结自动补一天)
      </NAlert>

      <!-- 回归引导 -->
      <NAlert v-if="showWelcomeBack" type="info">
        👋 欢迎回来！上次练习在 {{ gapDays }} 天前，从「🎯 练习」页的今日任务继续吧～
      </NAlert>

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
    </div>
  </NSpin>
</template>

<style scoped>
.subtitle {
  color: #666;
  margin-top: -8px;
}
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.cta-banner :deep(.n-card__content) {
  padding: 16px !important;
}
.cta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.cta-text {
  font-size: 14px;
  color: #555;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}
.xp-text {
  margin-bottom: 8px;
  font-size: 14px;
  color: #555;
}
.hint {
  color: #6B7280;
  font-size: 13px;
}
</style>
