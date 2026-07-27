<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NEmpty, NProgress } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { genCnOptions } from '@/utils/practiceOptions'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'
import type { PracticeQuestion } from '@/api/types'

// 限时挑战：单题 8 秒。超时算错（userAnswer=''）并立即推进，保持节奏；
// 点选项则停表、记录反应时、展示反馈，手动「下一题」。
// 忠实迁移自 frontend/pages/3_🎯_练习.py L1023-1078。
// 后端对 timed_challenge 按 word.chinese 服务端复判防伪造，故点击必须把所选 opt 作为 userAnswer 传回。
const TIME_LIMIT = 8

const store = usePracticeStore()
const { play } = useTtsAudio()

const remaining = ref(TIME_LIMIT)
const answered = ref(false) // 已点击选项 → 展示反馈（超时不展示，直接推进）
const finished = ref(false) // 当前题已处理（点击或超时），互斥锁防双触发
const selectedOpt = ref('')
const isCorrect = ref(false)
const rt = ref(0) // 反应时（秒）

// 选项按 word_id 缓存，进入该题惰性生成（同源页 tc_opts，批内不重算）
const optCache = ref(new Map<number, string[]>())
const opts = ref<string[]>([])

let intervalId: ReturnType<typeof setInterval> | null = null
let startTime = 0

const q = computed(() => store.currentQuestion)
const phonetic = computed(() => (q.value ? formatPhonetic(q.value.phonetic) : ''))
const isLast = computed(() => store.idx >= store.total - 1)
const progressPct = computed(() =>
  store.total > 0 ? Math.round((store.idx / store.total) * 100) : 0,
)
const countdownPct = computed(() =>
  Math.max(0, Math.min(100, Math.round((remaining.value / TIME_LIMIT) * 100))),
)
const countdownStatus = computed(() => {
  if (remaining.value > 4) return 'success'
  if (remaining.value > 2) return 'warning'
  return 'error'
})

function stopTimer() {
  if (intervalId != null) {
    clearInterval(intervalId)
    intervalId = null
  }
}

function startTimer() {
  stopTimer()
  startTime = Date.now()
  remaining.value = TIME_LIMIT
  // 真定时器：每 100ms 刷新 remaining；到 0 触发超时分支。onBeforeUnmount 必清，防离开后 submitOne。
  intervalId = setInterval(() => {
    const elapsed = (Date.now() - startTime) / 1000
    remaining.value = Math.max(0, TIME_LIMIT - elapsed)
    if (remaining.value <= 0) {
      stopTimer()
      onTimeout()
    }
  }, 100)
}

function resetForQuestion(newQ: PracticeQuestion) {
  answered.value = false
  finished.value = false
  selectedOpt.value = ''
  isCorrect.value = false
  rt.value = 0
  remaining.value = TIME_LIMIT
  const cached = optCache.value.get(newQ.word_id)
  if (cached) {
    opts.value = cached
  } else {
    const generated = genCnOptions(newQ, store.questions)
    optCache.value.set(newQ.word_id, generated)
    opts.value = generated
  }
  startTimer()
  void play(newQ.english)
}

function selectOption(opt: string) {
  if (finished.value) return
  const cur = q.value
  if (!cur) return
  finished.value = true
  stopTimer()
  const correct = opt === cur.chinese
  const reactionTime = (Date.now() - startTime) / 1000
  selectedOpt.value = opt
  isCorrect.value = correct
  rt.value = reactionTime
  answered.value = true
  // 客户端判定 opt===q.chinese；userAnswer 必传 opt 以便服务端复判
  void store.submitOne(cur.word_id, correct, opt)
}

function onTimeout() {
  if (finished.value) return
  const cur = q.value
  if (!cur) return
  finished.value = true
  isCorrect.value = false
  selectedOpt.value = ''
  rt.value = TIME_LIMIT
  // 超时算错，userAnswer=''（服务端按 word.chinese 复判，此处不伪造选项）
  void store.submitOne(cur.word_id, false, '')
  // 限时模式保持节奏：超时立即推进，不停在反馈页
  advance()
}

function advance() {
  const next = store.idx + 1
  if (next >= store.total) {
    store.setIdx(store.total)
  } else {
    store.setIdx(next)
  }
}

function optionType(opt: string): 'default' | 'success' | 'error' {
  if (!answered.value) return 'default'
  const cur = q.value
  if (!cur) return 'default'
  if (opt === cur.chinese) return 'success'
  if (opt === selectedOpt.value && !isCorrect.value) return 'error'
  return 'default'
}

async function onPlay() {
  const cur = q.value
  if (cur) await play(cur.english)
}

// 切题（store.idx 推进）即重置状态、重启倒计时。immediate 覆盖首题。
watch(
  () => store.currentQuestion?.word_id,
  () => {
    stopTimer()
    const newQ = store.currentQuestion
    if (!newQ) return
    resetForQuestion(newQ)
  },
  { immediate: true },
)

onBeforeUnmount(stopTimer)
</script>

<template>
  <div v-if="q" class="timed-challenge">
    <!-- 题号进度 -->
    <NProgress
      type="line"
      :percentage="progressPct"
      :show-indicator="false"
      :height="6"
      style="margin-bottom: 4px"
    />
    <p class="caption">第 {{ store.idx + 1 }} / {{ store.total }} 题</p>

    <!-- 倒计时（未答时显示） -->
    <div v-if="!answered" class="countdown">
      <NProgress
        type="line"
        :percentage="countdownPct"
        :status="countdownStatus"
        :show-indicator="false"
        :height="14"
        :border-radius="7"
      />
      <span class="countdown-text">⏱️ {{ remaining.toFixed(1) }}s</span>
    </div>

    <!-- 题干 -->
    <div class="word-head">
      <span class="english">{{ q.english }}</span>
      <NButton quaternary circle size="small" @click="onPlay">🔊</NButton>
    </div>
    <p v-if="phonetic" class="phonetic">{{ phonetic }}</p>

    <!-- 选项 -->
    <div class="options">
      <NButton
        v-for="(opt, i) in opts"
        :key="i"
        block
        :type="optionType(opt)"
        :disabled="answered"
        @click="selectOption(opt)"
      >
        {{ opt }}
      </NButton>
    </div>

    <!-- 反馈（点击路径；超时已推进，不展示） -->
    <NAlert v-if="answered" :type="isCorrect ? 'success' : 'error'" show-icon class="feedback">
      <span v-if="isCorrect">✅ 正确！反应 {{ rt.toFixed(1) }}s</span>
      <span v-else>
        ❌ 你的答案: {{ selectedOpt || '(超时)' }}　|　正确答案:
        <strong>{{ q.chinese }}</strong>
      </span>
    </NAlert>

    <!-- 下一题 -->
    <NButton v-if="answered" type="primary" block class="next-btn" @click="advance">
      {{ isLast ? '✅ 完成练习' : '➡️ 下一题' }}
    </NButton>
  </div>
  <NEmpty v-else description="本模式已完成" />
</template>

<style scoped>
.timed-challenge {
  max-width: 640px;
  margin: 0 auto;
}
.caption {
  color: #999;
  font-size: 13px;
  margin: 0 0 12px;
}
.countdown {
  margin-bottom: 16px;
}
.countdown-text {
  display: inline-block;
  margin-top: 4px;
  font-weight: 600;
  color: #666;
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
  margin: 0 0 16px;
  font-size: 15px;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.feedback {
  margin-bottom: 12px;
}
.next-btn {
  margin-top: 4px;
}
</style>
