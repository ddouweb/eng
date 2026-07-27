<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NCard, NEmpty, NSpace, NSpin, NStatistic, NTag, useMessage } from 'naive-ui'

import { api } from '@/api/client'
import type { WeeklySettlement } from '@/api/types'
import { BADGES } from '@/constants/badges'
import DimensionBar from '@/components/DimensionBar.vue'
import ScoreRing from '@/components/ScoreRing.vue'
import Stars from '@/components/Stars.vue'

// 本周结算（Phase A 新功能）：周分环 + 四维条 + 星 + bonus + plan_health + 对比上周 + 历史。
// 打开即懒结算上个完整周（后端 get_weekly_settlement 入口触发）。
const message = useMessage()
const history = ref<WeeklySettlement[]>([])
const loading = ref(true)

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

async function load() {
  loading.value = true
  const r = await api.getWeeklySettlement()
  if (r.code === 200) {
    history.value = r.data.history ?? []
  } else {
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

onMounted(load)
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🌟 本周结算</h2>
    <p class="subtitle">每周一张「学习周报卡」：坚持 / 难度 / 新词 / 计划 四维 + 星 + 坚持奖励（封顶 30 XP/周）。</p>

    <NEmpty v-if="!loading && !latest" description="尚无结算记录——打开本页会自动结算上一个完整的学习周。" style="margin-top: 40px" />

    <div v-if="latest" class="settle">
      <!-- 本周卡片 -->
      <NCard size="small">
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

      <!-- 计划体检 -->
      <NCard v-if="latest.plan_health" size="small" title="🩺 计划体检（考研进度）">
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
  color: #888;
  margin-top: -8px;
  font-size: 14px;
}
.settle {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  color: #999;
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
</style>
