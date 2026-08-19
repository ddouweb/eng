<script setup lang="ts">
// 抽卡奖励页（🎰 点石成金刮刮乐）：学习行为换抽卡次数，抽中金额进独立彩金账户。
// 页面状态机 mode: idle(总览) / single(刮单张) / batch(开一批)。
// 打开本页 = 懒同步单咽喉点（后端 /lottery/state 顺手补发 8 类条件次数），
// 其它页面绝不触发同步；批次续挂/单张续刮都从 state.active_batch/pending_single 恢复。
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NEmpty, NSpace, NSpin, NStatistic, useMessage } from 'naive-ui'
import { api } from '@/api/client'
import type { LotteryDrawData, LotteryStateData } from '@/api/types'
import { fmtPrize } from '@/constants/lottery'
import { useLotterySound } from '@/composables/useLotterySound'
import ScratchTicket from './ScratchTicket.vue'

const message = useMessage()
const sound = useLotterySound()

const loading = ref(true)
const state = ref<LotteryStateData | null>(null)
const mode = ref<'idle' | 'single'>('idle')
// 当前单张票（含全量票面）；outcome 非 null = 已开奖
const current = ref<LotteryDrawData | null>(null)
const outcome = ref<{ prize: number } | null>(null)
const drawing = ref(false)
const settling = ref(false)

const tasks = computed(() => state.value?.tasks ?? [])

async function loadState(): Promise<void> {
  const r = await api.getLotteryState()
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  state.value = r.data
}

/** 抽一张：出票即消耗次数，票面由后端定局 */
async function draw(): Promise<void> {
  drawing.value = true
  const r = await api.drawLottery()
  drawing.value = false
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  current.value = r.data
  outcome.value = null
  mode.value = 'single'
  if (state.value) state.value.draw_count = r.data.draw_count_left
}

/** 全部 25 格刮开：450ms 后自动结算入账（后端幂等，防双击/断网重试） */
async function onAllRevealed(): Promise<void> {
  const t = current.value
  if (!t) return
  settling.value = true
  setTimeout(async () => {
    const r = await api.settleLotteryTicket(t.id)
    settling.value = false
    if (r.code !== 200) {
      message.error(r.message)
      return
    }
    outcome.value = { prize: r.data.prize }
    if (state.value) {
      state.value.wealth = r.data.wealth
      state.value.draw_count = Math.max(0, state.value.draw_count)
    }
    await loadState() // 刷新战绩/历史/任务清单
  }, 450)
}

/** 再来一张 / 收起回到总览 */
function backToIdle(): void {
  mode.value = 'idle'
  current.value = null
  outcome.value = null
}

onMounted(async () => {
  await loadState()
  // 续刮：上次刮到一半关页的单张票（票据在后端，涂层是前端状态，重刮即可）
  const pending = state.value?.pending_single
  if (pending) {
    const r = await api.getLotteryTicket(pending.id)
    if (r.code === 200) {
      current.value = r.data
      outcome.value = null
      mode.value = 'single'
      message.info('接着上次的票继续刮～')
    }
  }
  loading.value = false
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🎰 抽卡奖励</h2>
    <p class="subtitle">学习行为换抽卡次数 · 中奖金额进独立彩金账户（与现金激励分开）</p>

    <!-- ── 刮票舞台（单张流）── -->
    <div v-if="mode === 'single' && current" class="stage">
      <ScratchTicket :ticket="current.ticket" :outcome="outcome" @all-revealed="onAllRevealed" />
      <div class="stage-actions">
        <template v-if="outcome">
          <NButton type="primary" :disabled="!state || state.draw_count < 1" @click="draw">
            再来一张（剩 {{ state?.draw_count ?? 0 }} 次）
          </NButton>
          <NButton quaternary @click="backToIdle">收起</NButton>
        </template>
        <template v-else>
          <NSpin v-if="settling" size="small" />
          <span v-else class="stage-hint">刮开全部 25 格涂层后自动开奖</span>
        </template>
      </div>
    </div>

    <!-- ── 总览（idle）── -->
    <template v-else>
      <!-- 顶部统计 + 抽卡入口 -->
      <NCard size="small" class="head-card">
        <div class="head-row">
          <div class="stats-row">
            <NStatistic label="可用次数" :value="state?.draw_count ?? 0" />
            <NStatistic label="彩金余额">
              <template #default>¥{{ fmtPrize(state?.wealth ?? 0) }}</template>
            </NStatistic>
            <NStatistic label="累计中奖">
              <template #default>¥{{ fmtPrize(state?.total_won ?? 0) }}</template>
            </NStatistic>
            <NStatistic label="中奖张数" :value="state?.hit_count ?? 0" />
          </div>
          <NSpace :size="8">
            <NButton type="primary" :loading="drawing" :disabled="!state || state.draw_count < 1" @click="draw">
              🎟️ 抽一张{{ state && state.draw_count > 0 ? `（剩 ${state.draw_count} 次）` : '' }}
            </NButton>
            <NButton quaternary :disabled="!state || state.draw_count < 1" title="开一批：整包抽卡，逐张核对开奖">
              🎴 开一批（敬请期待）
            </NButton>
            <NButton quaternary @click="sound.toggle()">
              {{ sound.enabled ? '🔊' : '🔇' }}
            </NButton>
          </NSpace>
        </div>
      </NCard>

      <!-- 任务清单：8 类获取条件 -->
      <NCard size="small" title="如何赚取抽卡次数" class="tasks-card">
        <div class="task-grid">
          <div v-for="t in tasks" :key="t.key" class="task-item" :class="{ done: t.done }">
            <div class="task-head">
              <span class="task-icon">{{ t.icon }}</span>
              <span class="task-title">{{ t.title }}</span>
              <span class="task-draws">+{{ t.draws }}</span>
            </div>
            <div class="task-rule">{{ t.rule }}</div>
            <div class="task-note">{{ t.note }}</div>
          </div>
        </div>
      </NCard>

      <!-- 最近战绩 -->
      <NCard size="small" title="最近战绩" class="history-card">
        <NEmpty
          v-if="!state || state.recent_tickets.length === 0"
          description="还没抽过卡——去赚次数开刮吧～"
        />
        <div v-else class="history-list">
          <div v-for="t in state.recent_tickets" :key="t.id" class="history-item">
            <span class="h-no">#{{ t.id }}</span>
            <span class="h-prize" :class="{ hit: t.prize > 0 }">
              {{ t.prize > 0 ? `中 ¥${fmtPrize(t.prize)}` : '未中' }}
            </span>
            <span class="h-batch" v-if="t.batch_id">🎴 批次</span>
            <span class="h-date">{{ (t.created_at ?? '').replace('T', ' ').slice(5, 16) }}</span>
            <span class="h-settled" :class="{ ok: t.settled_at }">{{ t.settled_at ? '已入账' : '待结算' }}</span>
          </div>
        </div>
      </NCard>
    </template>
  </NSpin>
</template>

<style scoped>
.subtitle {
  color: #888;
  margin-top: -8px;
}
.stage {
  max-width: 480px;
  margin: 0 auto;
}
.stage-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.stage-hint {
  color: #999;
  font-size: 13px;
}
.head-card {
  margin-bottom: 12px;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.stats-row {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}
.tasks-card {
  margin-bottom: 12px;
}
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.task-item {
  border: 1px solid #eaeaea;
  border-radius: 8px;
  padding: 10px 12px;
  opacity: 0.72;
}
.task-item.done {
  opacity: 1;
  border-color: #f0c060;
  background: rgba(245, 196, 81, 0.08);
}
.task-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.task-title {
  font-weight: 600;
}
.task-draws {
  margin-left: auto;
  color: #c23a28;
  font-weight: 700;
  font-size: 13px;
}
.task-rule {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
.task-note {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}
.history-card {
  margin-bottom: 12px;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
}
.history-item:hover {
  background: #fafafa;
}
.h-no {
  color: #aaa;
  min-width: 48px;
}
.h-prize {
  font-weight: 600;
  color: #999;
  min-width: 90px;
}
.h-prize.hit {
  color: #c23a28;
}
.h-batch {
  font-size: 12px;
  color: #b8860b;
}
.h-date {
  margin-left: auto;
  color: #aaa;
  font-size: 12px;
}
.h-settled {
  font-size: 12px;
  color: #bbb;
}
.h-settled.ok {
  color: #2f7d5b;
}
</style>
