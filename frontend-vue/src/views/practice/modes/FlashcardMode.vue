<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NSpace } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'

// 单词卡（源页 L650-771）。双路：
//  - auto（store.fcAutoNext）：点认识/不认识 → 立即 submitOne → 揭示中文 → 倒计时 fcDelay 秒自动下一题，
//    期间可手动「下一题」clearTimeout 抢先。
//  - manual：点按钮只置 pending（可反复改），「下一题」时才 submitOne + setIdx+1。
// 认识 → isCorrect=true / userAnswer=null；不认识 → isCorrect=false / userAnswer=english。
const store = usePracticeStore()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)

const answered = ref(false)
// manual 路径下的待定判定：true=认识 / false=不认识 / null=未选。
const pending = ref<boolean | null>(null)
// auto 路径倒计时剩余秒数（用于「⏱️ Xs 后自动下一题」展示）。
const autoRemaining = ref(0)
// 本题是否已前进（防 auto 倒计时到点与手动「下一题」竞态导致跳两题）。
const advanced = ref(false)

// 真 setTimeout/setInterval 句柄，onBeforeUnmount 与 goNext 必须清理（铁律）。
// 用 window.* 走 DOM 签名（返回 number），规避 @types/node 的 NodeJS.Timeout 歧义。
let displayTimer: number | null = null
let advanceTimer: number | null = null

const isLast = computed(() => store.idx >= store.total - 1)
const phoneticDisplay = computed(() => formatPhonetic(q.value?.phonetic))

function clearTimers() {
  if (displayTimer !== null) {
    window.clearInterval(displayTimer)
    displayTimer = null
  }
  if (advanceTimer !== null) {
    window.clearTimeout(advanceTimer)
    advanceTimer = null
  }
}

function goNext() {
  if (advanced.value) return
  advanced.value = true
  clearTimers()
  store.setIdx(isLast.value ? store.total : store.idx + 1)
}

// auto 路径：答后启动倒计时；到点自动下一题。displayTimer 每 100ms 刷新剩余秒数展示。
function startAutoCountdown() {
  clearTimers()
  const delaySec = Math.max(0, store.fcDelay)
  const start = Date.now()
  autoRemaining.value = delaySec
  displayTimer = window.setInterval(() => {
    const elapsed = (Date.now() - start) / 1000
    autoRemaining.value = Math.max(0, delaySec - elapsed)
  }, 100)
  advanceTimer = window.setTimeout(() => {
    goNext()
  }, delaySec * 1000)
}

function replay() {
  const cur = store.currentQuestion
  if (cur) void play(cur.english)
}

function onAnswer(recognized: boolean) {
  const cur = store.currentQuestion
  if (!cur || answered.value) return
  answered.value = true
  if (store.fcAutoNext) {
    // auto：立即提交，揭示中文，启动倒计时。
    void store.submitOne(cur.word_id, recognized, recognized ? null : cur.english)
    startAutoCountdown()
  } else {
    // manual：仅置 pending，可反复改，下一题时才提交。
    pending.value = recognized
  }
}

function togglePending(recognized: boolean) {
  if (answered.value && !store.fcAutoNext) {
    pending.value = recognized
  }
}

function confirmManualNext() {
  if (!answered.value || store.fcAutoNext) return
  const rec = pending.value
  if (rec === null) return
  const cur = store.currentQuestion
  if (!cur) return
  void store.submitOne(cur.word_id, rec, rec ? null : cur.english)
  goNext()
}

// 进入新题：清旧定时器 + 重置本地态 + 自动播放音频。
watch(
  () => store.idx,
  () => {
    clearTimers()
    answered.value = false
    pending.value = null
    autoRemaining.value = 0
    advanced.value = false
    const cur = store.currentQuestion
    if (cur) void play(cur.english)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <div v-if="q" class="flashcard-mode">
    <div class="word-line">
      <span class="word">{{ q.english }}</span>
      <span v-if="phoneticDisplay" class="phonetic">{{ phoneticDisplay }}</span>
      <NButton size="small" quaternary circle @click="replay">🔊</NButton>
    </div>

    <NSpace v-if="!answered" :size="12">
      <NButton size="large" type="primary" @click="onAnswer(true)">✅ 认识</NButton>
      <NButton size="large" @click="onAnswer(false)">❌ 不认识</NButton>
    </NSpace>

    <div v-else class="reveal">
      <NAlert type="info">
        <b>{{ q.chinese }}</b>
      </NAlert>

      <template v-if="store.fcAutoNext">
        <p class="caption">⏱️ {{ autoRemaining.toFixed(1) }}s 后自动下一题</p>
        <NButton type="primary" @click="goNext">➡️ 下一题</NButton>
      </template>

      <template v-else>
        <NSpace :size="12">
          <NButton
            :type="pending === true ? 'primary' : 'default'"
            @click="togglePending(true)"
          >
            {{ pending === true ? '✅ 已标记：认识' : '✅ 认识' }}
          </NButton>
          <NButton
            :type="pending === false ? 'primary' : 'default'"
            @click="togglePending(false)"
          >
            {{ pending === false ? '❌ 已标记：不认识' : '❌ 不认识' }}
          </NButton>
        </NSpace>
        <NButton type="primary" :disabled="pending === null" @click="confirmManualNext">
          ➡️ 下一题
        </NButton>
      </template>
    </div>
  </div>
  <div v-else class="empty">暂无题目</div>
</template>

<style scoped>
.flashcard-mode {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}
.word-line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.word {
  font-size: 26px;
  font-weight: 700;
}
.phonetic {
  color: #888;
  font-size: 16px;
}
.reveal {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
}
.caption {
  color: #888;
  font-size: 14px;
  margin: 0;
}
.empty {
  color: #999;
}
</style>
