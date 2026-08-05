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
  NTooltip,
  useDialog,
  useMessage,
} from 'naive-ui'

import { api } from '@/api/client'
import type { CheckinEncouragement, ReviewDue, StatsProfile, StatsToday, WeekProgress } from '@/api/types'
import { BADGES, type BadgeMeta } from '@/constants/badges'
import DimensionBar from '@/components/DimensionBar.vue'

// 完整仪表盘（批次 5）：指标卡 / XP 进度 / 断签预警 / 回归引导 / 徽章 / 今日到期复习。
// 忠实迁移自 frontend/app.py 的首页仪表盘部分。
const message = useMessage()
const router = useRouter()
const dialog = useDialog()

const profile = ref<StatsProfile | null>(null)
const reviewDue = ref<ReviewDue | null>(null)
const today = ref<StatsToday | null>(null)
const week = ref<WeekProgress | null>(null)
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

// 是否展示「计划体检」右栏：active 计划且 plan_health 非空。
// 模板复用此判断（v-if 右栏 + 决定单栏/双栏布局），避免重复长表达式。
const showPlanHealth = computed(
  () => !!today.value?.has_active_plan && !!today.value?.plan_health,
)

// 已获徽章集合（O(1) 判定）+ 首次获得时间映射 + 徽章总数：徽章区全量展示，
// 命中此处者点亮、其余置灰，hover 显示获得条件与时间，标题展示「已获 X / N」。
const earnedBadgeSet = computed<Set<string>>(
  () => new Set((profile.value?.badges ?? []).map((b) => b.key)),
)
const awardedAtMap = computed<Map<string, string>>(() => {
  const m = new Map<string, string>()
  for (const b of profile.value?.badges ?? []) {
    if (b.awarded_at) m.set(b.key, b.awarded_at.slice(0, 10))
  }
  return m
})
const badgeTotal = computed(() => Object.keys(BADGES).length)
// 徽章排序：已获得排前（按获得时间升序，早的在前），未获得排后（保持定义顺序）。
const sortedBadges = computed(() => {
  const earned: Array<{ key: string; meta: BadgeMeta }> = []
  const locked: Array<{ key: string; meta: BadgeMeta }> = []
  for (const [key, meta] of Object.entries(BADGES)) {
    if (earnedBadgeSet.value.has(key)) earned.push({ key, meta })
    else locked.push({ key, meta })
  }
  earned.sort((a, b) =>
    (awardedAtMap.value.get(a.key) ?? '').localeCompare(awardedAtMap.value.get(b.key) ?? ''),
  )
  return [...earned, ...locked]
})

// 本周进度差距文案（激励向）：已断天数 / 剩余全勤日 / 新词缺口 / 计划完成率，拼一句。
const weekGap = computed<string>(() => {
  const w = week.value
  if (!w) return ''
  const parts: string[] = []
  if (w.login_lost_days > 0) {
    parts.push(`坚持已断 ${w.login_lost_days} 天`)
  } else if (w.login_remaining_days > 0) {
    parts.push(`坚持再保持 ${w.login_remaining_days} 天即满分`)
  }
  const newGap = Math.max(0, w.weekly_new_target - w.new_words)
  if (newGap > 0) parts.push(`新词还差 ${newGap} 个`)
  if (w.planned_slots > 0 && w.plan_completion < 1) {
    parts.push(`计划完成 ${Math.round(w.plan_completion * 100)}%`)
  }
  if (!parts.length) return '🎉 本周已拿满分，保持住！'
  return '💡 ' + parts.join(' · ') + ' 可提升本周结算'
})

// 智能建议（首页顶部唯一主提示，按优先级取一条）：
// 断签风险 > 长期回归 > 无计划 > 今日缺口 > 节奏偏慢 > 已完成
// 断签/回归提示折叠进此 alert，避免顶部出现多条黄色提示。
const advice = computed<{ type: 'info' | 'warning' | 'success'; text: string } | null>(() => {
  const p = profile.value
  const t = today.value
  const g = gapDays.value
  // 1) 今天还没活跃且连胜未断：最紧急（今晚可能断签）
  if (p && g !== null && g > 0 && p.current_streak > 0) {
    const wb = g >= 3 ? `👋 欢迎回来！上次练习在 ${g} 天前。` : ''
    return {
      type: 'warning',
      text: `${wb}⚠️ 你已连续 ${p.current_streak} 天，今天还没练习——别让记录断在今晚！`,
    }
  }
  // 2) 长期回归但已无连胜可保：鼓励重新开始
  if (g !== null && g >= 3) {
    return {
      type: 'info',
      text: `👋 欢迎回来！上次练习在 ${g} 天前，从「🎯 练习」继续吧～`,
    }
  }
  if (!t) return null
  // 3) 无学习计划
  if (!t.has_active_plan) {
    return {
      type: 'info',
      text: '还没有「学新词」学习计划，去 📅 学习计划 创建一个，系统会自动排好每日新词与复习。',
    }
  }
  // 4) 今日有缺口
  const newGap = Math.max(0, t.today_new_target - t.today_new_done)
  const revGap = Math.max(0, t.today_review_target - t.today_review_done)
  if (newGap > 0 || revGap > 0) {
    return {
      type: 'warning',
      text: `今天还差 ${newGap} 个新词、${revGap} 个复习待完成，去 🎯 练习 吧！`,
    }
  }
  // 5) 节奏偏慢（on_track 提示由 advice 承担，卡片内不再重复）
  const h = t.plan_health
  if (h && h.on_track === false) {
    return {
      type: 'warning',
      text: `当前节奏可能在 deadline 前背不完，建议每日新词 ${h.suggested_daily_goal ?? '?'} 个（去 📅 学习计划 点「重新平衡」）。`,
    }
  }
  // 6) 全部完成
  return { type: 'success', text: '🎉 今天的任务都完成啦，节奏不错！' }
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
  // profile 是主数据：失败 → 进入错误态（可重试）。reviewDue/today 是辅助数据：失败仅 toast，不阻塞整页。
  const [profileResp, reviewResp, todayResp, weekResp] = await Promise.all([
    api.getStatsProfile(),
    api.getReviewDue(),
    api.getStatsToday(),
    api.getStatsWeekProgress(),
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
  if (todayResp.code === 200) {
    today.value = todayResp.data
  } else {
    message.error(`今日完成情况加载失败：${todayResp.message}`)
  }
  if (weekResp.code === 200) {
    week.value = weekResp.data
  } else {
    message.error(`本周进度加载失败：${weekResp.message}`)
  }
  loading.value = false
}

// ── 每日签到：AI 励学寄语 → 用户确认 → 标记今日活跃（保住 streak，不加 XP）。
// gapDays===0 表示今日已活跃（练过或签过），按钮禁用；同日重复签到后端幂等 no-op。
const checkinLoading = ref(false)

async function onCheckin() {
  if (checkinLoading.value) return
  checkinLoading.value = true
  const r = await api.checkinEncouragement()
  checkinLoading.value = false
  // 后端 best-effort：AI 成功→个性化寄语；AI 不可用→真实学习概况。两者都有实质内容。
  // 仅当接口本身挂了（网络/500）才退极简静态文案，但弹窗照常、可继续签到。
  const enc: CheckinEncouragement =
    r.code === 200 && r.data
      ? r.data
      : { title: '今日寄语', message: '坚持就是胜利！今天也来学一点，保持你的节奏吧 💪' }
  // AI 不可用时标题用 📊 区分（内容是真实学习数据，非 AI 生成）
  const title = enc.ai_used === false ? `📊 ${enc.title}` : `✅ ${enc.title}`
  dialog.info({
    title,
    content: enc.message,
    positiveText: '确认签到',
    negativeText: '再想想',
    onPositiveClick: () => {
      void doCheckin()
    },
  })
}

async function doCheckin() {
  const r = await api.checkin()
  if (r.code === 200) {
    message.success(
      r.data.first_active_today
        ? `签到成功！已连续 ${r.data.current_streak} 天 🔥`
        : '今日已活跃，明天再来吧～',
    )
    await load() // 刷新 streak / freeze / 按钮态
  } else {
    message.error(r.message)
  }
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
            <NButton
              :loading="checkinLoading"
              :disabled="gapDays === 0"
              @click="onCheckin"
            >{{ gapDays === 0 ? '✅ 今日已签到' : '✅ 每日签到' }}</NButton>
            <NButton @click="goPlans">📅 学习计划</NButton>
          </NSpace>
        </div>
      </NCard>

      <!-- 顶部唯一主提示（断签/回归/无计划/缺口/节奏/完成，按优先级取一条） -->
      <NAlert v-if="advice" :type="advice.type" :bordered="false">{{ advice.text }}</NAlert>

      <!-- 本周进度（实时预估，激励用：本周截至今天能拿多少分 + 还差什么） -->
      <NCard v-if="week" size="small">
        <template #header>📊 本周进度</template>
        <template #header-extra>
          <span class="week-key">{{ week.week_key }} · 进行中</span>
        </template>
        <div class="week-summary">
          <span class="stars">{{ '⭐'.repeat(week.stars) }}<span class="star-empty">{{ '☆'.repeat(5 - week.stars) }}</span></span>
          <b>{{ week.total_score }}</b><span class="dim-suffix">分</span>
          <span class="dim-suffix">· 预计 +{{ week.bonus_xp }} XP</span>
          <span v-if="week.cash_enabled && week.cash_reward > 0" class="cash">· 预估 ¥{{ week.cash_reward }}</span>
          <span v-else-if="week.cash_enabled && week.total_score < 100" class="cash-hint">· 冲满分拿现金</span>
        </div>
        <div class="week-dims">
          <DimensionBar label="坚持" icon="🔥" :score="week.login_score" :max="week.login_full" color="#18a058" />
          <DimensionBar label="新词" icon="🌱" :score="week.new_score" :max="week.new_full" color="#2080f0" />
          <DimensionBar label="计划" icon="📅" :score="week.plan_score" :max="week.plan_full" color="#f0a020" />
        </div>
        <p class="hint" style="margin: 0">{{ weekGap }}</p>
      </NCard>

      <!-- 今日进度：今日任务（左）+ 计划体检（右）合并为一张两栏卡 -->
      <NCard v-if="today" size="small" title="📊 今日进度">
        <div class="today-grid" :class="{ 'single-col': !showPlanHealth }">
          <!-- 左栏：今日任务 + 实际练习量 -->
          <div class="today-col">
            <div class="col-title">今日任务</div>
            <template v-if="today.has_active_plan">
              <DimensionBar
                label="新词"
                icon="🌱"
                :score="today.today_new_done"
                :max="today.today_new_target"
                color="#2080f0"
              />
              <DimensionBar
                label="复习"
                icon="🔁"
                :score="today.today_review_done"
                :max="today.today_review_target"
                color="#f0a020"
              />
            </template>
            <p v-else class="hint" style="margin: 0 0 10px">
              还没有学习计划，今日无任务（去 📅 学习计划 创建）
            </p>
            <div class="today-stats">
              <NStatistic label="今日答对" :value="today.today_correct" />
              <NStatistic label="今日新词" :value="today.today_new_words" />
              <NStatistic label="错题待处理" :value="today.wrong_book_total" />
            </div>
          </div>
          <!-- 右栏：计划体检（实时，以今天为基准；无 active 计划时整栏隐藏，左栏占满） -->
          <div v-if="showPlanHealth" class="today-col">
            <div class="col-title">计划体检</div>
            <NStatistic label="剩余未掌握" :value="today.plan_health!.remaining_unmastered" />
            <NStatistic
              v-if="today.plan_health!.remaining_learn_days !== null"
              label="剩余学习日"
              :value="today.plan_health!.remaining_learn_days"
            />
            <NStatistic
              v-if="today.plan_health!.suggested_daily_goal !== null"
              label="建议每日新词"
              :value="today.plan_health!.suggested_daily_goal"
            />
            <NStatistic
              v-if="today.plan_health!.projected_finish"
              label="预计学完"
              :value="today.plan_health!.projected_finish"
            />
          </div>
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

      <!-- 徽章墙：默认显示图标+名称；hover 显示获得条件与获取时间 -->
      <NCard size="small" :title="`🎖️ 徽章 · 已获 ${earnedBadgeSet.size} / ${badgeTotal}`">
        <div class="badge-grid">
          <NTooltip
            v-for="{ key, meta } in sortedBadges"
            :key="key"
            trigger="hover"
            placement="top"
          >
            <template #trigger>
              <div
                class="badge-chip"
                :class="earnedBadgeSet.has(key) ? 'earned' : 'locked'"
              >
                <span class="badge-emoji">{{ meta.icon }}</span>
                <span class="badge-label">{{ meta.name }}</span>
              </div>
            </template>
            <div style="max-width: 200px">
              <div>{{ meta.desc }}</div>
              <div v-if="earnedBadgeSet.has(key) && awardedAtMap.has(key)" style="margin-top: 4px; font-size: 12px; opacity: 0.85">
                🏆 {{ awardedAtMap.get(key) }}
              </div>
            </div>
          </NTooltip>
        </div>
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
  gap: 12px;
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
  gap: var(--card-gap);
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
.badge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(66px, 1fr));
  gap: 8px;
}
.badge-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 4px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: default;
  transition: transform 0.12s ease;
}
.badge-chip:hover {
  transform: translateY(-2px);
}
.badge-emoji {
  font-size: 24px;
  line-height: 1;
}
.badge-label {
  font-size: 11px;
  line-height: 1.2;
  text-align: center;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* 点亮：浅绿底 + 绿边框 + 彩色图标 + 深绿加粗名（与未点亮强对比） */
.badge-chip.earned {
  background: #dcfce7;
  border-color: #22c55e;
}
.badge-chip.earned .badge-label {
  color: #15803d;
  font-weight: 600;
}
/* 未点亮：灰白底 + 灰度透明图标 + 浅灰名 */
.badge-chip.locked {
  background: #f5f5f5;
}
.badge-chip.locked .badge-emoji {
  filter: grayscale(1);
  opacity: 0.4;
}
.badge-chip.locked .badge-label {
  color: #b0b0b0;
}
/* 今日进度：左右两栏；窄屏堆叠；无计划体检时单栏占满 */
.today-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 36px;
}
.today-grid.single-col {
  grid-template-columns: 1fr;
}
.today-col {
  display: flex;
  flex-direction: column;
}
.today-col .col-title {
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
}
.today-col :deep(.n-statistic) {
  margin-bottom: 6px;
}
.today-stats {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid #f0f0f0;
}
/* 本周进度卡 */
.week-key {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}
.week-summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  color: #555;
  margin-bottom: 4px;
}
.week-summary .stars {
  letter-spacing: 1px;
}
.week-summary .star-empty {
  color: #d0d4dc;
}
.week-summary .dim-suffix {
  color: #909399;
  font-size: 13px;
}
.week-summary .cash {
  color: #e0548f;
  font-weight: 600;
}
.week-summary .cash-hint {
  color: #e0548f;
  font-size: 13px;
}
.week-dims {
  margin-top: 4px;
}
@media (max-width: 720px) {
  .today-grid {
    grid-template-columns: 1fr;
  }
}
</style>
