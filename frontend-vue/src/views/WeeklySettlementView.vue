<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NCollapse, NCollapseItem, NEmpty, NSpace, NSpin, NStatistic, NTag, useMessage } from 'naive-ui'

import { api } from '@/api/client'
import type { CashMilestone, WeeklySettlement } from '@/api/types'
import { BADGES } from '@/constants/badges'
import { milestoneDisplay, tierLabel } from '@/constants/cash'
import DimensionBar from '@/components/DimensionBar.vue'
import ScoreRing from '@/components/ScoreRing.vue'
import Stars from '@/components/Stars.vue'
import EChart from '@/components/EChart.vue'
import { CHART_HEIGHT } from '@/constants/ui'
import type { EChartsOption } from 'echarts'

// 本周结算：周分环 + 四维条 + 星 + bonus + 现金激励（周学习现金 + 里程碑奖金）+ plan_health + 历史。
// 打开即懒结算上个完整周（后端 get_weekly_settlement 入口触发；CASH_ENABLED 时一并懒发放里程碑）。
const message = useMessage()
const history = ref<WeeklySettlement[]>([])
const cashBalance = ref(0)
const cashEnabled = ref(false)
const milestones = ref<CashMilestone[]>([])
const loading = ref(true)
const loadError = ref(false)

const latest = computed<WeeklySettlement | null>(() => history.value[0] ?? null)
const prev = computed<WeeklySettlement | null>(() => history.value[1] ?? null)

// total 对比上周（正负）
const totalDelta = computed(() => {
  if (!latest.value || !prev.value) return null
  return latest.value.total_score - prev.value.total_score
})

interface Dim {
  label: string
  icon: string
  score: number
  max: number
  color: string
}
const dims = computed<Dim[]>(() => {
  const s = latest.value
  if (!s) return []
  return [
    { label: '坚持', icon: '🔥', score: s.login_score, max: 25, color: '#18a058' },
    { label: '难度', icon: '🧗', score: s.difficulty_score, max: 25, color: '#f0a020' },
    { label: '新词', icon: '🌱', score: s.new_score, max: 20, color: '#2080f0' },
    { label: '计划', icon: '📅', score: s.plan_score, max: 30, color: '#7c3aed' },
  ]
})

// 历史周分趋势：x=week_key（旧→新），y=总分(0-100) 折线，叠加星点（右轴 0-5）。
// history 为 latest-first，趋势按时间正序故 reverse；颜色复用本页既有四维配色（蓝=分、橙=星）。
const trendOption = computed<EChartsOption>(() => {
  const rows = [...history.value].reverse()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['周总分', '星'], top: 0, textStyle: { color: '#6B7280' } },
    grid: { left: 36, right: 36, top: 36, bottom: 24, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((h) => h.week_key),
      axisLabel: { color: '#6B7280' },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '总分',
        min: 0,
        max: 100,
        nameTextStyle: { color: '#6B7280' },
        axisLabel: { color: '#6B7280' },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
      },
      {
        type: 'value',
        name: '星',
        min: 0,
        max: 5,
        nameTextStyle: { color: '#6B7280' },
        axisLabel: { color: '#6B7280', formatter: '{value}★' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '周总分',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#2080f0' },
        lineStyle: { color: '#2080f0', width: 3 },
        areaStyle: { color: 'rgba(32,128,240,0.12)' },
        data: rows.map((h) => h.total_score),
        label: { show: true, color: '#374151', fontWeight: 600 },
      },
      {
        name: '星',
        type: 'scatter',
        yAxisIndex: 1,
        symbol: 'star',
        symbolSize: 16,
        itemStyle: { color: '#f0a020' },
        data: rows.map((h) => h.stars),
      },
    ],
  }
})

async function load() {
  loading.value = true
  loadError.value = false
  const r = await api.getWeeklySettlement()
  if (r.code === 200) {
    history.value = r.data.history ?? []
    cashBalance.value = r.data.cash_balance ?? 0
    cashEnabled.value = r.data.cash_enabled ?? false
    milestones.value = r.data.milestones ?? []
  } else {
    loadError.value = true
    message.error(r.message)
  }
  loading.value = false
}

function badgeName(key: string): string {
  return BADGES[key]?.name ?? key
}
function badgeIcon(key: string): string {
  return BADGES[key]?.icon ?? '🏅'
}

// 现金额度格式化：始终两位小数。
function yuan(n: number): string {
  return (n ?? 0).toFixed(2)
}

onMounted(load)
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🌟 本周结算</h2>
    <p class="subtitle">每周一张「学习周报卡」：四维评分 → 星 + XP；开启现金激励后另发周学习现金 + 里程碑奖金，累计进虚拟钱包。</p>

    <NCollapse class="logic" :default-expanded-names="[]">
      <NCollapseItem title="📖 结算逻辑简述（怎么算分 / 怎么发钱）" name="logic">
        <ul class="logic-list">
          <li><b>四维评分</b>（满分 100）：坚持 25 + 难度 25 + 新词 20 + 计划 30 → 周总分 → 星 = round(总分/20)，0~5 星。</li>
          <li><b>XP 奖励</b>：答对逐题得 XP（含难度系数）；周结算另发 bonus XP（仅坚持+计划派生，封顶 30/周）。</li>
          <li><b>周学习现金</b>（开启后）：按星 + 计划完成度分档——5★+满计划 ¥50 / 5★ ¥40 / 4★+满计划 ¥30 / 4★ ¥20 / 3★ ¥10；≤2 星不发，封顶 ¥50/周。</li>
          <li><b>里程碑奖金</b>（开启后）：背完一个 Unit / 累计掌握 N 词 / 连续 N 周全勤，达标即发、每项终身一次。</li>
          <li>两项现金<b>累计进虚拟钱包</b>，线下兑现；系统只记账，不建兑现流水。</li>
          <li><b>防重复</b>：周现金奖「每周质量」、里程碑奖「离散成就」，奖励不同的事不重复支付；已发放金额不因后续回退扣回（snapshot 语义）。</li>
        </ul>
      </NCollapseItem>
    </NCollapse>

    <NEmpty v-if="loadError && !loading" description="结算数据加载失败" style="margin-top: 40px">
      <template #extra>
        <NButton size="small" @click="load">🔄 重试</NButton>
      </template>
    </NEmpty>
    <NEmpty v-else-if="!loading && !latest && !cashEnabled" description="尚无结算记录——打开本页会自动结算上一个完整的学习周。" style="margin-top: 40px" />

    <div v-if="latest || cashEnabled" class="settle">
      <!-- 本周卡片 -->
      <NCard v-if="latest" size="small">
        <div class="week-head">
          <div>
            <div class="week-key">{{ latest.week_key }}</div>
            <div class="week-range">{{ latest.week_start }} ~ {{ latest.week_end }}</div>
          </div>
          <Stars :count="latest.stars" />
        </div>

        <div class="top">
          <ScoreRing :score="latest.total_score" />
          <div class="dims">
            <DimensionBar
              v-for="d in dims"
              :key="d.label"
              :label="d.label"
              :icon="d.icon"
              :score="d.score"
              :max="d.max"
              :color="d.color"
            />
          </div>
        </div>

        <!-- 奖励 -->
        <div class="rewards">
          <NStatistic label="坚持奖励" :value="`+${latest.bonus_xp} XP`" />
          <NStatistic label="断签冻结" :value="`+${latest.freeze_granted}`" />
          <NStatistic label="真实学习" :value="`${latest.real_days} 天`" />
          <NStatistic label="本周新词" :value="latest.new_words_learned" />
          <NStatistic label="计划完成" :value="`${Math.round(latest.plan_completion * 100)}%`" />
        </div>

        <!-- 对比上周 -->
        <NAlert v-if="totalDelta !== null" :type="totalDelta >= 0 ? 'success' : 'warning'" class="delta">
          <template v-if="totalDelta >= 0">▲ 比上周高 <b>{{ totalDelta }}</b> 分，继续保持！</template>
          <template v-else>▼ 比上周低 <b>{{ -totalDelta }}</b> 分，下周加油～</template>
        </NAlert>

        <!-- 新获徽章 -->
        <div v-if="latest.badges_granted.length" class="badges">
          <span class="badge-label">本周新获：</span>
          <NTag v-for="b in latest.badges_granted" :key="b" type="success" round :bordered="false">
            {{ badgeIcon(b) }} {{ badgeName(b) }}
          </NTag>
        </div>
      </NCard>

      <!-- 💰 现金奖励（虚拟钱包） -->
      <NCard v-if="cashEnabled" size="small">
        <div class="cash-head">💰 现金奖励（虚拟钱包）</div>
        <div class="cash-stats">
          <NStatistic v-if="latest" label="本周现金" :value="`¥${yuan(latest.cash_reward)}`" />
          <NStatistic label="累计钱包" :value="`¥${yuan(cashBalance)}`" />
          <template v-if="latest">
            <div v-if="latest.cash_tier_label" class="tier-tag">
              <NTag type="warning" round :bordered="false">{{ tierLabel(latest.cash_tier_label) }}</NTag>
            </div>
            <div v-else class="tier-tag"><NTag :bordered="false" round>本周未达现金档</NTag></div>
          </template>
        </div>
      </NCard>
      <NAlert v-else type="info" :bordered="false" class="cash-off">
        💡 现金激励未开启——管理员可在后端 <code>.env</code> 设 <code>CASH_ENABLED=true</code> 启用周学习现金与里程碑奖金。
      </NAlert>

      <!-- 🏆 现金里程碑奖金 -->
      <NCard v-if="cashEnabled && milestones.length" size="small">
        <div class="cash-head">🏆 里程碑奖金 <span class="cash-sub">（达标即发 · 终身一次）</span></div>
        <div class="milestone-list">
          <div v-for="m in milestones" :key="m.milestone_key" class="milestone-row">
            <span class="m-icon">{{ milestoneDisplay(m).icon }}</span>
            <span class="m-title">{{ milestoneDisplay(m).title }}</span>
            <span class="m-amount">+¥{{ yuan(m.amount) }}</span>
            <span v-if="m.granted_at" class="m-date">{{ m.granted_at.slice(0, 10) }}</span>
          </div>
        </div>
      </NCard>

      <!-- 计划体检 -->
      <NCard v-if="latest && latest.plan_health" size="small" title="🩺 计划体检（考研进度）">
        <NSpace :size="24" wrap>
          <NStatistic label="剩余未掌握" :value="latest.plan_health.remaining_unmastered" />
          <NStatistic
            v-if="latest.plan_health.remaining_learn_days !== null"
            label="剩余学习日"
            :value="latest.plan_health.remaining_learn_days"
          />
          <NStatistic
            v-if="latest.plan_health.suggested_daily_goal !== null"
            label="建议每日新词"
            :value="latest.plan_health.suggested_daily_goal"
          />
          <NStatistic
            v-if="latest.plan_health.projected_finish"
            label="预计学完"
            :value="latest.plan_health.projected_finish"
          />
        </NSpace>
        <NAlert
          v-if="latest.plan_health.on_track !== null"
          :type="latest.plan_health.on_track ? 'success' : 'warning'"
          style="margin-top: 12px"
        >
          <template v-if="latest.plan_health.on_track">✅ 按当前节奏可在 deadline 前背完</template>
          <template v-else>⚠️ 当前节奏可能在 deadline 前背不完，考虑去「📅 学习计划」点「重新平衡」</template>
        </NAlert>
      </NCard>

      <!-- 历史 -->
      <NCard v-if="history.length > 1" size="small" title="📜 历史周报">
        <div class="trend-wrap">
          <EChart :option="trendOption" :height="CHART_HEIGHT.lg" />
        </div>
        <div class="history">
          <div v-for="h in history" :key="h.week_key" class="hist-row">
            <span class="hist-key">{{ h.week_key }}</span>
            <Stars :count="h.stars" />
            <span class="hist-total">{{ h.total_score }} 分</span>
            <span class="hist-bonus">+{{ h.bonus_xp }} XP</span>
          </div>
        </div>
      </NCard>
    </div>
  </NSpin>
</template>

<style scoped>
.subtitle {
  color: #6B7280;
  margin-top: -8px;
  font-size: 13px;
}
.settle {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 760px;
}
.week-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.week-key {
  font-size: 20px;
  font-weight: 700;
}
.week-range {
  color: #6B7280;
  font-size: 13px;
}
.top {
  display: flex;
  gap: 32px;
  align-items: center;
  flex-wrap: wrap;
}
.dims {
  flex: 1;
  min-width: 260px;
}
.rewards {
  display: flex;
  gap: 28px;
  flex-wrap: wrap;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
.delta {
  margin-top: 14px;
}
.badges {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.badge-label {
  color: #666;
  font-size: 14px;
}
.history {
  display: flex;
  flex-direction: column;
}
.trend-wrap {
  margin-bottom: 12px;
}
.hist-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}
.hist-key {
  width: 90px;
  font-variant-numeric: tabular-nums;
  color: #555;
}
.hist-total {
  margin-left: auto;
  font-weight: 600;
}
.hist-bonus {
  color: #18a058;
  width: 70px;
  text-align: right;
}
.logic {
  max-width: 760px;
  margin-bottom: 16px;
}
.logic-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
  color: #555;
  font-size: 14px;
}
.logic-list b {
  color: #222;
}
.cash-head {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}
.cash-sub {
  font-size: 12px;
  font-weight: 400;
  color: #6B7280;
}
.cash-stats {
  display: flex;
  gap: 32px;
  align-items: center;
  flex-wrap: wrap;
}
.tier-tag {
  margin-left: auto;
}
.cash-off {
  max-width: 760px;
}
.cash-off code {
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 13px;
}
.milestone-list {
  display: flex;
  flex-direction: column;
}
.milestone-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid #f5f5f5;
}
.milestone-row:last-child {
  border-bottom: none;
}
.m-icon {
  font-size: 18px;
}
.m-title {
  flex: 1;
  color: #333;
}
.m-amount {
  color: #18a058;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.m-date {
  color: #6B7280;
  font-size: 12px;
  width: 84px;
  text-align: right;
}
</style>
