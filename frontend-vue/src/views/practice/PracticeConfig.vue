<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  useMessage,
  type SelectOption,
} from 'naive-ui'

import { api } from '@/api/client'
import { PRACTICE_MODES } from '@/constants/modes'
import { usePracticeStore } from '@/stores/practice'
import type { DailyTask, Unit } from '@/api/types'

const emit = defineEmits<{ started: [] }>()
const store = usePracticeStore()
const message = useMessage()

const units = ref<Unit[]>([])
const wbCount = ref(0)
const selectedIds = ref<number[]>([])
const COUNTS = [10, 20, 30, 50, 80, 100, 150, 200, '全部'] as const
const countChoice = ref<number | '全部'>(50)
const resolvedCount = computed(() => (countChoice.value === '全部' ? 2000 : countChoice.value))

const unitOptions = computed<SelectOption[]>(() => [
  { label: `📕 错题本（${wbCount.value}）`, value: 0 },
  ...units.value.map((u) => ({ label: u.title, value: u.id })),
])

// 需要干扰项的选择类模式：session 词数 <2 时退化为单选项（点唯一即对），启动前拦截。
const OPTIONS_MODES = new Set(['cn2en_choice', 'timed_challenge', 'memory_flash'])
function ensureEnoughForMode(mode: string): boolean {
  if (OPTIONS_MODES.has(mode) && store.questions.length < 2) {
    message.warning('题量不足以生成选项，请改用拼写/闪卡模式或增加 Unit')
    store.restart()
    return false
  }
  return true
}

async function startMode(mode: string) {
  if (!selectedIds.value.length) {
    message.warning('请至少选择一个 Unit（或错题本）')
    return
  }
  const r = await store.start(mode, [...selectedIds.value], resolvedCount.value)
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  if (!ensureEnoughForMode(mode)) return
  emit('started')
}

// ── 今日计划聚合（spec §3.3）──
interface PlanSnap {
  planId: number
  planName: string
  unitIds: number[]
  tasks: Record<string, DailyTask>
}
const snapshot = ref<PlanSnap[]>([])
const todayMode = ref('flashcard')
// 本地时区日期（YYYY-MM-DD），与后端 date.today() 服务端本地口径对齐。
// 切勿用 toISOString()——它取 UTC 日期，UTC+8 零点后 8 小时会与后端 task_date 错配漏掉今日任务。
const todayStr = new Date().toLocaleDateString('sv-SE')
const dueN = ref(0)
const overdue = ref(0)

const modeOptions = computed<SelectOption[]>(() =>
  PRACTICE_MODES.map((m) => ({ label: `${m.icon} ${m.label}`, value: m.value })),
)

const agg = computed(() => {
  const aggUnitIds = new Set<number>()
  let learnNew = 0
  let learnReview = 0
  let weekly = 0
  let monthly = 0
  let drill = 0
  let hasLearn = false
  let learnDone = true
  let hasWeekly = false
  let weeklyDone = true
  let hasMonthly = false
  let monthlyDone = true
  let hasDrill = false
  let drillDone = true
  for (const s of snapshot.value) {
    s.unitIds.forEach((id) => id && aggUnitIds.add(id))
    const t = s.tasks
    if (t.learn) {
      hasLearn = true
      learnNew += Math.max(t.learn.new_count - t.learn.completed_new, 0)
      learnReview += Math.max(t.learn.review_count - t.learn.completed_review, 0)
      if (t.learn.status !== 'completed') learnDone = false
    }
    if (t.weekly_review) {
      hasWeekly = true
      weekly += Math.max(t.weekly_review.review_count - t.weekly_review.completed_review, 0)
      if (t.weekly_review.status !== 'completed') weeklyDone = false
    }
    if (t.monthly_review) {
      hasMonthly = true
      monthly += Math.max(t.monthly_review.review_count - t.monthly_review.completed_review, 0)
      if (t.monthly_review.status !== 'completed') monthlyDone = false
    }
    if (t.wrong_word_drill) {
      hasDrill = true
      drill += Math.max(t.wrong_word_drill.review_count - t.wrong_word_drill.completed_review, 0)
      if (t.wrong_word_drill.status !== 'completed') drillDone = false
    }
  }
  return {
    aggUnitIds: [...aggUnitIds],
    learnTotal: learnNew + learnReview,
    weekly,
    monthly,
    drill,
    hasLearn,
    learnDone,
    hasWeekly,
    weeklyDone,
    hasMonthly,
    monthlyDone,
    hasDrill,
    drillDone,
  }
})

async function launch(taskType: string | undefined, count: number, label: string) {
  const ids = agg.value.aggUnitIds
  if (!ids.length) {
    message.warning('今日没有可练习的计划任务')
    return
  }
  const r = await store.start(todayMode.value, ids, Math.max(count, 5), taskType)
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  if (!ensureEnoughForMode(todayMode.value)) return
  message.info(`开始：${label}`)
  emit('started')
}

async function loadToday() {
  const plans = await api.listPlans('active')
  if (plans.code !== 200) return
  const snaps: PlanSnap[] = []
  for (const p of plans.data) {
    const det = await api.getPlan(p.id)
    if (det.code !== 200) continue
    const todayTasks = (det.data.tasks ?? []).filter((t) => t.task_date === todayStr)
    const byType: Record<string, DailyTask> = {}
    for (const t of todayTasks) if (!byType[t.task_type]) byType[t.task_type] = t
    snaps.push({ planId: p.id, planName: p.name, unitIds: det.data.unit_ids ?? [], tasks: byType })
  }
  snapshot.value = snaps
  const rd = await api.getReviewDue(agg.value.aggUnitIds.length ? agg.value.aggUnitIds : undefined)
  if (rd.code === 200) {
    dueN.value = rd.data.due_today
    overdue.value = rd.data.overdue
  }
}

onMounted(async () => {
  const [u, wb] = await Promise.all([api.listAllUnits(), api.countWrongBook()])
  if (u.code === 200) units.value = u.data.items
  if (wb.code === 200) wbCount.value = wb.data.total
  await loadToday()
})
</script>

<template>
  <div class="prac-config">
    <h2 style="margin-top: 0">🎯 练习</h2>

    <!-- 今日任务快捷入口 -->
    <NCard v-if="snapshot.length" size="small" title="📌 今日任务" class="block">
      <NSpace align="center" wrap style="margin-bottom: 12px">
        <span class="field">练习模式</span>
        <NSelect v-model:value="todayMode" :options="modeOptions" style="width: 220px" />
      </NSpace>
      <NSpace wrap>
        <NButton
          v-if="dueN > 0"
          type="warning"
          @click="launch(undefined, dueN, '今日到期复习')"
        >
          🔁 今日到期复习（{{ dueN }}<template v-if="overdue">，逾期 {{ overdue }}</template>）
        </NButton>
        <NButton
          v-if="agg.hasLearn && !agg.learnDone && agg.learnTotal > 0"
          type="primary"
          @click="launch('learn', agg.learnTotal, '今日学习')"
        >
          🚀 开始今日学习（剩 {{ agg.learnTotal }}）
        </NButton>
        <NButton
          v-if="agg.hasWeekly && !agg.weeklyDone && agg.weekly > 0"
          @click="launch('weekly_review', agg.weekly, '本周复习')"
        >
          📖 本周复习（剩 {{ agg.weekly }}）
        </NButton>
        <NButton
          v-if="agg.hasMonthly && !agg.monthlyDone"
          @click="launch('monthly_review', agg.monthly, '本月复习')"
        >
          📚 本月复习（剩 {{ agg.monthly }}）
        </NButton>
        <NButton
          v-if="agg.hasDrill && !agg.drillDone"
          @click="launch('wrong_word_drill', agg.drill, '错题冲刺')"
        >
          🎯 错题冲刺（剩 {{ agg.drill }}）
        </NButton>
      </NSpace>
    </NCard>

    <!-- 自由练习配置 -->
    <NCard size="small" title="🎮 自由练习" class="block">
      <NSpace vertical :size="14">
        <NSpace align="center" wrap>
          <span class="field">选择 Unit</span>
          <NSelect
            v-model:value="selectedIds"
            multiple
            :options="unitOptions"
            placeholder="可多选（含错题本）"
            style="min-width: 360px"
          />
        </NSpace>

        <NSpace align="center" wrap>
          <span class="field">数量</span>
          <NButton
            v-for="c in COUNTS"
            :key="String(c)"
            size="small"
            :type="countChoice === c ? 'primary' : 'default'"
            @click="countChoice = c"
          >
            {{ c }}
          </NButton>
        </NSpace>

        <NSpace align="center" wrap>
          <span class="field">单词卡</span>
          <NSwitch v-model:value="store.fcAutoNext" />
          <span style="font-size: 13px; color: #888">自动下一题</span>
          <template v-if="store.fcAutoNext">
            <span style="font-size: 13px; color: #888">延时</span>
            <NInputNumber v-model:value="store.fcDelay" :min="0.5" :max="10" :step="0.5" size="small" style="width: 90px" />
            <span style="font-size: 13px; color: #888">秒</span>
          </template>
        </NSpace>

        <div class="mode-grid">
          <div
            v-for="m in PRACTICE_MODES"
            :key="m.value"
            class="mode-card"
            :class="{ disabled: !selectedIds.length }"
            @click="startMode(m.value)"
          >
            <div class="mode-icon">{{ m.icon }}</div>
            <div class="mode-label">{{ m.label }}</div>
          </div>
        </div>
        <p v-if="!selectedIds.length" class="hint">请先选择至少一个 Unit（或错题本）</p>
      </NSpace>
    </NCard>

    <NTag v-if="snapshot.length" :bordered="false" type="info">
      今日计划已聚合 {{ snapshot.length }} 个，涉及 {{ agg.aggUnitIds.length }} 个 Unit
    </NTag>
  </div>
</template>

<style scoped>
.prac-config {
  max-width: 860px;
}
.block {
  margin-bottom: 16px;
}
.field {
  display: inline-block;
  min-width: 64px;
  color: #666;
  font-size: 14px;
}
.mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
}
.mode-card {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 16px 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-card:hover {
  border-color: #18a058;
  background: #f0faf3;
}
.mode-card.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.mode-card.disabled:hover {
  border-color: #e0e0e0;
  background: transparent;
}
.mode-icon {
  font-size: 26px;
}
.mode-label {
  margin-top: 6px;
  font-size: 13px;
  color: #444;
}
.hint {
  color: #d03050;
  font-size: 13px;
}
</style>
