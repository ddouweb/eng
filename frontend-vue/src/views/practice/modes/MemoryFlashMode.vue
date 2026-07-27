<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NEmpty,
  NProgress,
  NRadio,
  NRadioGroup,
  NSpace,
  useMessage,
} from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { genCnOptions } from '@/utils/practiceOptions'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'

// 记忆闪卡：批量 BATCH=4，两阶段 study（逐张记忆）→ quiz（回忆测试）。
// 忠实迁移自 frontend/pages/3_🎯_练习.py L1118-1176。
// 无定时器；切题由用户点击驱动，故无需 onBeforeUnmount 清理。
const BATCH = 4

const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const batch = ref(0)
const phase = ref<'study' | 'quiz'>('study')
const idx = ref(0) // 批内下标
const answer = ref<string | null>(null)

// quiz 阶段每题作答结果（批内有效，换批清空）
const quizAns = ref(new Map<number, { answer: string; correct: boolean }>())
// 选项按 word_id 惰性生成并缓存（跨批保留，同源页 mf_opts_{wid}）
const optCache = ref(new Map<number, string[]>())
const opts = ref<string[]>([])

const total = computed(() => store.total)
const startI = computed(() => batch.value * BATCH)
const endI = computed(() => Math.min(startI.value + BATCH, total.value))
const batchQuestions = computed(() => store.questions.slice(startI.value, endI.value))
const currentQ = computed(() => batchQuestions.value[idx.value] ?? null)
const phonetic = computed(() => (currentQ.value ? formatPhonetic(currentQ.value.phonetic) : ''))
const currentDone = computed(() => {
  const q = currentQ.value
  return !!q && quizAns.value.has(q.word_id)
})
const currentResult = computed(() => {
  const q = currentQ.value
  if (!q) return null
  return quizAns.value.get(q.word_id) ?? null
})
const batchProgressPct = computed(() => {
  const len = batchQuestions.value.length
  if (len === 0) return 0
  return Math.round(((idx.value + 1) / len) * 100)
})

// 当前题切换（word_id 或 phase 变化）：刷新选项 + 自动播放音频。
// 依赖必须含 phase：单题批次（total%4===1）study→quiz 切换时 word_id 不变（w0→w0），
// 若只监听 word_id，Vue 同 tick 合并后判定未变化 → refreshOpts 不触发 → quiz 选项空 → 卡死。
watch(
  () => [currentQ.value?.word_id, phase.value],
  () => {
    refreshOpts()
    if (store.autoPlay) void playCurrent()
  },
  { immediate: true },
)

function refreshOpts() {
  if (phase.value !== 'quiz') {
    opts.value = []
    return
  }
  const q = currentQ.value
  if (!q) {
    opts.value = []
    return
  }
  const cached = optCache.value.get(q.word_id)
  if (cached) {
    opts.value = cached
    return
  }
  const generated = genCnOptions(q, store.questions)
  optCache.value.set(q.word_id, generated)
  opts.value = generated
}

async function playCurrent() {
  const q = currentQ.value
  if (q) await play(q.english, store.fcSpeed)
}

// 细粒度推进顶栏进度（store.idx）：本批起点 + 已答 quiz 数。
// 仅最后一批最后一题答完才可能 = total → 触发 isDone，不会提前结束。
function syncProgress() {
  store.setIdx(Math.min(batch.value * BATCH + quizAns.value.size, store.total))
}

function onAnswerChange(v: string | number | boolean | null): void {
  answer.value = v == null ? null : String(v)
}

// study → 下一张；idx 越过本批 → 进 quiz
function nextStudyCard() {
  idx.value += 1
  if (idx.value >= batchQuestions.value.length) {
    phase.value = 'quiz'
    idx.value = 0
  }
}

function confirmQuiz() {
  const q = currentQ.value
  if (!q || currentDone.value) return
  if (answer.value == null) {
    message.warning('请先选择一个答案')
    return
  }
  const correct = answer.value === q.chinese
  quizAns.value.set(q.word_id, { answer: answer.value, correct })
  void store.submitOne(q.word_id, correct, answer.value)
  syncProgress()
}

// quiz → 下一题；本批 quiz 结束 → 换批回 study；越界 → 完成
function nextQuiz() {
  answer.value = null
  idx.value += 1
  if (idx.value >= batchQuestions.value.length) {
    const nextBatch = batch.value + 1
    const newStart = nextBatch * BATCH
    if (newStart >= total.value) {
      // 越界：无更多词，结束
      store.setIdx(total.value)
      return
    }
    batch.value = nextBatch
    phase.value = 'study'
    idx.value = 0
    quizAns.value = new Map()
    store.setIdx(Math.min(newStart, total.value))
  }
}
</script>

<template>
  <div v-if="currentQ" class="memory-flash">
    <!-- 批次/进度 -->
    <div class="batch-meta">
      <span>第 {{ batch + 1 }} 批（{{ startI + 1 }}–{{ endI }} / {{ total }}）</span>
      <span class="phase-tag">{{ phase === 'study' ? '📚 记忆' : '🧠 测试' }}</span>
    </div>
    <NProgress
      type="line"
      :percentage="batchProgressPct"
      :show-indicator="false"
      :height="6"
      style="margin-bottom: 16px"
    />

    <!-- study 阶段：逐张记忆 -->
    <div v-if="phase === 'study'" class="study">
      <NAlert type="info" :show-icon="false" class="phase-banner">
        📚 记住这些单词！（{{ idx + 1 }} / {{ batchQuestions.length }}）
      </NAlert>
      <div class="word-head">
        <span class="english">{{ currentQ.english }}</span>
        <NButton quaternary circle size="small" @click="playCurrent">🔊</NButton>
      </div>
      <p v-if="phonetic" class="phonetic">{{ phonetic }}</p>
      <div class="chinese">{{ currentQ.chinese }}</div>
      <NButton type="primary" block class="next-btn" @click="nextStudyCard">
        下一张 ➡️
      </NButton>
    </div>

    <!-- quiz 阶段：回忆测试 -->
    <div v-else class="quiz">
      <NAlert type="warning" :show-icon="false" class="phase-banner">
        🧠 回忆测试（{{ idx + 1 }} / {{ batchQuestions.length }}）
      </NAlert>
      <div class="word-head">
        <span class="english">{{ currentQ.english }}</span>
        <NButton quaternary circle size="small" @click="playCurrent">🔊</NButton>
      </div>
      <p v-if="phonetic" class="phonetic">{{ phonetic }}</p>

      <NRadioGroup
        :value="answer"
        :disabled="currentDone"
        class="options"
        @update:value="onAnswerChange"
      >
        <NSpace vertical :size="8">
          <NRadio v-for="(opt, i) in opts" :key="i" :value="opt">{{ opt }}</NRadio>
        </NSpace>
      </NRadioGroup>

      <!-- 反馈 -->
      <NAlert
        v-if="currentDone && currentResult"
        :type="currentResult.correct ? 'success' : 'error'"
        show-icon
        class="feedback"
      >
        <span v-if="currentResult.correct">✅ 记忆力不错！</span>
        <span v-else>
          ❌ 忘了吗？正确答案: <strong>{{ currentQ.chinese }}</strong>
        </span>
      </NAlert>

      <!-- 操作按钮 -->
      <NButton v-if="!currentDone" type="primary" block class="next-btn" @click="confirmQuiz">
        确认
      </NButton>
      <NButton v-else type="primary" block class="next-btn" @click="nextQuiz">
        ➡️ 下一题
      </NButton>
    </div>
  </div>
  <NEmpty v-else description="本模式已完成" />
</template>

<style scoped>
.memory-flash {
  margin: 0 auto;
}
.batch-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #888;
  font-size: 13px;
  margin-bottom: 6px;
}
.phase-tag {
  font-weight: 600;
  color: #555;
}
.phase-banner {
  margin-bottom: 16px;
}
.word-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.english {
  font-size: 26px;
  font-weight: 700;
}
.phonetic {
  color: #888;
  margin: 0 0 12px;
  font-size: 15px;
}
.chinese {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 20px;
}
.options {
  margin-bottom: 16px;
}
.feedback {
  margin-bottom: 12px;
}
.next-btn {
  margin-top: 4px;
}
</style>
