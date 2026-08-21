<script setup lang="ts">
// 抽卡奖励页（🎰 点石成金刮刮乐）：学习行为换抽卡次数，抽中金额进独立彩金账户。
// 页面状态机 mode: idle(总览) / single(刮一张) / batch(批次网格)。
// 打开本页 = 懒同步单咽喉点（后端 /lottery/state 顺手补发 8 类条件次数）。
// 单张流：刮完 25 格自动开奖；批次流：刮完进核对态，玩家自查票面后手动开奖（原版同款）。
// 续挂：刷新后 state.pending_single 续刮单张、state.active_batch 续挂批次（票据在后端）。
import { computed, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NEmpty,
  NInputNumber,
  NModal,
  NRadio,
  NRadioGroup,
  NSpace,
  NSpin,
  NStatistic,
  useMessage,
} from 'naive-ui'
import { api } from '@/api/client'
import type { BatchSummary, LotteryDrawData, LotteryStateData } from '@/api/types'
import { calcOddsStats, fmtPrize } from '@/constants/lottery'
import { useLotterySound } from '@/composables/useLotterySound'
import BatchBoard from './BatchBoard.vue'
import ScratchTicket from './ScratchTicket.vue'

const message = useMessage()
const sound = useLotterySound()

const loading = ref(true)
const state = ref<LotteryStateData | null>(null)
type Mode = 'idle' | 'single' | 'batch'
const mode = ref<Mode>('idle')
// 当前挂刮的票（含全量票面）；outcome 非 null = 已开奖
const current = ref<LotteryDrawData | null>(null)
const outcome = ref<{ prize: number } | null>(null)
// 批次票刮完进入核对态（不自动开奖，玩家自查后点「核对结果」）
const verifying = ref(false)
const drawing = ref(false)
const settling = ref(false)

// ── 开一批弹窗（项目首个 NModal：10/20/50/自定义 1~500）──
const batchModalShow = ref(false)
const batchPick = ref(10)
const batchCustom = ref(10)
const batchOpening = ref(false)
const odds = calcOddsStats()

const tasks = computed(() => state.value?.tasks ?? [])
const batchCount = computed(() => (batchPick.value > 0 ? batchPick.value : batchCustom.value))
// 挂刮中的票是否批次票（决定刮完自动开奖还是进核对态）
const inBatch = computed(() => current.value?.batch_id != null)

// 批次网格数据（active_batch 续挂 / 开批后加载）
const batchSummary = ref<BatchSummary | null>(null)

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
  verifying.value = false
  mode.value = 'single'
  if (state.value) state.value.draw_count = r.data.draw_count_left
}

/** 全部 25 格刮开：单张自动开奖（450ms）；批次进核对态等玩家自查 */
function onAllRevealed(): void {
  if (inBatch.value) {
    verifying.value = true
    return
  }
  const t = current.value
  if (!t) return
  settling.value = true
  setTimeout(() => void doSettle(t.id), 450)
}

/** 结算入账（后端幂等）；更新彩金/战绩并刷新总览 */
async function doSettle(ticketId: number): Promise<void> {
  const r = await api.settleLotteryTicket(ticketId)
  settling.value = false
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  outcome.value = { prize: r.data.prize }
  if (state.value) state.value.wealth = r.data.wealth
  // 批次票：顺手刷新批次网格（settle 响应只带回摘要子集，重取全量含 tickets）
  if (batchSummary.value) await loadBatch(batchSummary.value.batch_id)
  await loadState()
}

/** 核对结果 → 手动开奖（批次票） */
function verify(): void {
  const t = current.value
  if (!t) return
  verifying.value = false
  settling.value = true
  void doSettle(t.id)
}

async function loadBatch(batchId: string): Promise<void> {
  const r = await api.getLotteryBatch(batchId)
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  batchSummary.value = r.data
  mode.value = 'batch'
}

/** 开一批（NModal 确认）：开批即定局，只回 id 清单，悬念在逐张核对 */
async function openBatch(): Promise<void> {
  const count = batchCount.value
  if (!Number.isInteger(count) || count < 1 || count > 500) {
    message.warning('批次数量须在 1~500 之间')
    return
  }
  batchOpening.value = true
  const r = await api.drawLotteryBatch(count)
  batchOpening.value = false
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  batchModalShow.value = false
  if (state.value) state.value.draw_count = r.data.draw_count_left
  await loadBatch(r.data.batch_id)
}

/** 点批次网格里的一张未结算卡 → 取票挂刮 */
async function pickTicket(ticketId: number): Promise<void> {
  const r = await api.getLotteryTicket(ticketId)
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  current.value = r.data
  outcome.value = null
  verifying.value = false
  mode.value = 'single'
}

/** 批次里随机挑一张未结算的挂刮 */
function pickRandom(): void {
  const pending = batchSummary.value?.tickets.filter((t) => !t.settled) ?? []
  if (!pending.length) return
  const t = pending[Math.floor(Math.random() * pending.length)]
  void pickTicket(t.id)
}

/** 从单张舞台返回：批次票回批次网格（未核对完），单张票回总览（进行中的批次经提示条再进） */
function backFromTicket(): void {
  const wasBatchTicket = current.value?.batch_id != null
  current.value = null
  outcome.value = null
  verifying.value = false
  mode.value = wasBatchTicket && batchSummary.value && batchSummary.value.remaining > 0 ? 'batch' : 'idle'
}

function dropBatch(): void {
  batchSummary.value = null
  mode.value = 'idle'
}

onMounted(async () => {
  // 只加载总览，不自动进入舞台——续挂票/批次经总览提示条主动进入
  // （票据持久化在后端，何时续刮都不丢；此前一进来就被续挂票顶到刮票舞台，
  //   想看战绩/彩金总览被卡住）
  await loadState()
  loading.value = false
})

// 总览提示条：有未完成的对局（批次优先 > 单张续刮）时显示续挂入口
const resumable = computed<
  | { text: string; action: () => void }
  | null
>(() => {
  const active = state.value?.active_batch
  if (active && active.remaining > 0) {
    return {
      text: `🎴 有一批 ${active.size} 张进行中（剩 ${active.remaining} 张未核对）`,
      action: () => {
        batchSummary.value = active
        mode.value = 'batch'
      },
    }
  }
  const pending = state.value?.pending_single
  if (pending) {
    return {
      text: `🎟️ 有一张未刮完的票（#${pending.id}），涂层进度不保留、重刮即可`,
      action: () => void pickTicket(pending.id),
    }
  }
  return null
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🎰 抽卡奖励</h2>
    <p class="subtitle">学习行为换抽卡次数 · 中奖金额进独立彩金账户（与现金激励分开）</p>

    <!-- ── 刮票舞台（单张 / 批次挂卡共用）：深色红金底，样式贴原版游戏页 ── -->
    <div v-if="mode === 'single' && current" class="stage">
      <!-- :key 按票 id 强制重挂载：刮层/计数器只在挂载时建一次，「再来一张」换票
           若复用旧实例，新票会直接全裸（旧涂层已清空）且永不触发 allRevealed -->
      <ScratchTicket
        :key="current.id"
        :ticket="current.ticket"
        :outcome="outcome"
        @all-revealed="onAllRevealed"
      />
      <div class="stage-actions">
        <!-- 批次票：刮完进核对态，先自查票面再手动开奖 -->
        <template v-if="inBatch">
          <template v-if="verifying">
            <button class="btn" :disabled="settling" @click="verify">
              {{ settling ? '⏳ 核对中…' : '🔍 核对结果 · 开奖' }}
            </button>
            <button class="btn-ghost" :disabled="settling" @click="backFromTicket">暂不核对，回本批</button>
          </template>
          <template v-else-if="outcome">
            <button class="btn" @click="backFromTicket">
              {{ batchSummary && batchSummary.remaining > 0 ? '回到本批' : '本批刮完了 · 看战报' }}
            </button>
            <button
              class="btn-ghost"
              :disabled="!batchSummary || batchSummary.remaining < 1"
              @click="pickRandom"
            >
              随机再来一张
            </button>
          </template>
          <template v-else>
            <span class="stage-hint">刮开全部 25 格后，先自己核对票面，再点「核对结果」开奖</span>
            <button class="btn-ghost" @click="backFromTicket">稍后再刮，回总览</button>
          </template>
        </template>
        <!-- 单张票：刮完自动开奖 -->
        <template v-else>
          <template v-if="outcome">
            <button class="btn" :disabled="!state || state.draw_count < 1" @click="draw">
              再来一张（剩 {{ state?.draw_count ?? 0 }} 次）
            </button>
            <button class="btn-ghost" @click="backFromTicket">收起</button>
          </template>
          <template v-else>
            <NSpin v-if="settling" size="small" />
            <span v-else class="stage-hint">刮开全部 25 格涂层后自动开奖</span>
            <button class="btn-ghost" @click="backFromTicket">稍后再刮，回总览</button>
          </template>
        </template>
      </div>
    </div>

    <!-- ── 批次网格 ── -->
    <div v-else-if="mode === 'batch' && batchSummary" class="stage">
      <BatchBoard :summary="batchSummary" @pick="pickTicket" />
      <div class="stage-actions">
        <!-- 批次挂卡消耗的是开批时已付的次数，这里不再看 draw_count -->
        <button v-if="batchSummary.remaining > 0" class="btn" @click="pickRandom">
          随机刮一张（本批剩 {{ batchSummary.remaining }} 张）
        </button>
        <button v-else class="btn" @click="dropBatch">本批完成，收起战报</button>
        <button class="btn-ghost" @click="dropBatch">收起本批</button>
      </div>
    </div>

    <!-- ── 总览（idle）── -->
    <template v-else>
      <!-- 续挂提示：有未完成的对局（批次/未刮完的单张），主动点击才进入 -->
      <NAlert v-if="resumable" type="info" :bordered="false" class="resume-alert">
        <div class="resume-row">
          <span>{{ resumable.text }}</span>
          <NButton size="small" type="primary" @click="resumable.action">继续 →</NButton>
        </div>
      </NAlert>

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
            <NButton
              type="primary"
              :loading="drawing"
              :disabled="!state || state.draw_count < 1"
              @click="draw"
            >
              🎟️ 抽一张{{ state && state.draw_count > 0 ? `（剩 ${state.draw_count} 次）` : '' }}
            </NButton>
            <NButton
              :disabled="!state || state.draw_count < 2"
              @click="batchModalShow = true"
              title="整包抽卡，逐张核对开奖，战报一目了然"
            >
              🎴 开一批
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

    <!-- ── 开一批弹窗 ── -->
    <NModal v-model:show="batchModalShow" preset="card" title="🎴 开一批" style="width: 420px">
      <NSpace vertical :size="12">
        <NRadioGroup v-model:value="batchPick">
          <NSpace>
            <NRadio :value="10">10 张</NRadio>
            <NRadio :value="20">20 张</NRadio>
            <NRadio :value="50">50 张</NRadio>
            <NRadio :value="0">自定义</NRadio>
          </NSpace>
        </NRadioGroup>
        <NInputNumber
          v-if="batchPick === 0"
          v-model:value="batchCustom"
          :min="1"
          :max="500"
          :disabled="state ? batchCustom > state.draw_count : false"
          style="width: 160px"
        >
          <template #suffix>张</template>
        </NInputNumber>
        <p class="batch-estimate">
          这批 {{ batchCount }} 张：按真实赔率（中奖率约 {{ Math.round(odds.hitRate * 100) }}%、返还率约
          {{ Math.round(odds.rtp * 100) }}%），期望中奖合计约 ¥{{ fmtPrize(batchCount * odds.rtp * 20) }}
          ——开批即定局，先刮后刮都一样。
        </p>
        <NSpace justify="end">
          <NButton quaternary @click="batchModalShow = false">取消</NButton>
          <NButton
            type="primary"
            :loading="batchOpening"
            :disabled="!state || batchCount < 1 || batchCount > (state?.draw_count ?? 0)"
            @click="openBatch"
          >
            开批（用 {{ batchCount }} 次）
          </NButton>
        </NSpace>
      </NSpace>
    </NModal>
  </NSpin>
</template>

<style scoped>
.subtitle {
  color: #888;
  margin-top: -8px;
}
.resume-alert {
  margin-bottom: 12px;
}
.resume-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
/* 舞台 = 原版游戏页的红金暗底（body 渐变照抄），票面/批次卡浮在上面才有原版气质 */
.stage {
  max-width: 560px;
  margin: 0 auto;
  padding: 14px 14px 18px;
  border: 1px solid rgba(245, 196, 81, 0.3);
  border-radius: 14px;
  background:
    radial-gradient(1200px 600px at 50% -100px, rgba(198, 40, 40, 0.45), transparent 70%),
    linear-gradient(180deg, #3d0d0d 0%, #2a0606 55%, #1d0404 100%);
  color: #fff9ea;
}
.stage-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.stage-hint {
  color: #cdb98d;
  font-size: 13px;
}
/* 舞台按钮 = 原版 .btn / .btn-ghost（红渐变圆角 + 金边幽灵） */
.btn {
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  padding: 11px 26px;
  border-radius: 999px;
  background: linear-gradient(180deg, #e8553f, #b9301c);
  box-shadow: 0 4px 14px rgba(183, 49, 28, 0.45);
  transition:
    transform 0.12s,
    box-shadow 0.12s;
}
.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(183, 49, 28, 0.55);
}
.btn:active:not(:disabled) {
  transform: translateY(1px);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-ghost {
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  color: #f5c451;
  padding: 8px 18px;
  border-radius: 999px;
  border: 2px solid rgba(245, 196, 81, 0.7);
  background: transparent;
  transition: background 0.15s;
}
.btn-ghost:hover:not(:disabled) {
  background: rgba(245, 196, 81, 0.12);
}
.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
.batch-estimate {
  font-size: 13px;
  color: #8a6d3b;
  background: rgba(245, 196, 81, 0.12);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 0;
}
</style>
