<script setup lang="ts">
// 英→中选择。源页 L774-819。服务端预生成 q.options，前端只读。
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NProgress,
  NRadio,
  NRadioGroup,
  useMessage,
} from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'

const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)
const answered = computed(() => (q.value ? store.results.has(q.value.word_id) : false))
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)
const options = computed(() => {
  const qv = q.value
  if (!qv) return [] as string[]
  return qv.options && qv.options.length ? qv.options : [qv.chinese]
})
const progressPct = computed(() =>
  store.total ? Math.round((store.idx / store.total) * 100) : 0,
)

const selected = ref<string | null>(null)
// 上一题回访时从 store.results 复原所选；进入新题清空。
watch(
  () => q.value?.word_id,
  () => {
    selected.value = entry.value?.userAnswer ?? null
  },
  { immediate: true },
)

function onPlay() {
  if (q.value) void play(q.value.english)
}

async function onSubmit() {
  const qv = q.value
  if (!qv) return
  if (selected.value == null) {
    message.warning('请先选择一个答案')
    return
  }
  const correct = selected.value === qv.chinese
  await store.submitOne(qv.word_id, correct, selected.value)
}

function goPrev() {
  if (store.idx > 0) store.setIdx(store.idx - 1)
}
function goNext() {
  if (store.idx < store.total - 1) store.setIdx(store.idx + 1)
  else store.setIdx(store.total)
}
</script>

<template>
  <div class="mode-wrap">
    <NCard size="medium">
      <div class="prog">
        <span class="prog-text">第 {{ store.idx + 1 }} / {{ store.total }} 题</span>
        <NProgress :percentage="progressPct" :show-indicator="false" />
      </div>

      <div v-if="q" class="body">
        <div class="word-line">
          <span class="word">{{ q.english }}</span>
          <NButton size="small" quaternary @click="onPlay">🔊 播放</NButton>
        </div>

        <p class="opt-label">选择正确的中文释义：</p>
        <NRadioGroup v-model:value="selected" :disabled="answered">
          <div class="opt-list">
            <NRadio v-for="opt in options" :key="opt" :value="opt">{{ opt }}</NRadio>
          </div>
        </NRadioGroup>

        <template v-if="!answered">
          <div class="actions">
            <NButton type="primary" @click="onSubmit">确认</NButton>
          </div>
        </template>
        <template v-else>
          <NAlert :type="isCorrect ? 'success' : 'error'" show-icon class="feedback">
            <template v-if="isCorrect">✅ 正确！</template>
            <template v-else>
              ❌ 你的答案：{{ entry?.userAnswer }}　|　正确答案：<strong>{{ q.chinese }}</strong>
            </template>
          </NAlert>

          <div class="nav-row">
            <NButton :disabled="store.idx === 0" @click="goPrev">⬅️ 上一题</NButton>
            <NButton v-if="store.idx < store.total - 1" type="primary" @click="goNext">
              ➡️ 下一题
            </NButton>
            <NButton v-else type="primary" @click="goNext">✅ 完成练习</NButton>
          </div>
        </template>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.mode-wrap {
  max-width: 720px;
  margin: 0 auto;
}
.prog {
  margin-bottom: 16px;
}
.prog-text {
  display: block;
  color: #888;
  font-size: 13px;
  margin-bottom: 6px;
}
.word-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.word {
  font-size: 28px;
  font-weight: 700;
}
.opt-label {
  margin: 0 0 8px;
  color: #555;
}
.opt-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.actions {
  margin-top: 16px;
}
.feedback {
  margin: 16px 0 12px;
}
.nav-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
</style>
