<script setup lang="ts">
// 英→中默写。源页 L903-927。精确、大小写敏感（trim 后比对，源 L913 strip）。
// 题面已展示 english+音标+音频，故答后不再揭示富字段。源页无「上一题」、无空值校验。
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NInput,
  NProgress,
} from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'

const store = usePracticeStore()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)
const answered = computed(() => (q.value ? store.results.has(q.value.word_id) : false))
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)
const progressPct = computed(() =>
  store.total ? Math.round((store.idx / store.total) * 100) : 0,
)
const phonetic = computed(() => formatPhonetic(q.value?.phonetic))

const answer = ref('')
watch(
  () => q.value?.word_id,
  () => {
    answer.value = entry.value?.userAnswer ?? ''
  },
  { immediate: true },
)

function onPlay() {
  if (q.value) void play(q.value.english)
}

async function onSubmit() {
  const qv = q.value
  if (!qv) return
  const ans = answer.value.trim()
  const correct = ans === qv.chinese
  await store.submitOne(qv.word_id, correct, ans)
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
          <span v-if="phonetic" class="phon">{{ phonetic }}</span>
          <NButton size="small" quaternary @click="onPlay">🔊 播放</NButton>
        </div>

        <NInput
          v-model:value="answer"
          :disabled="answered"
          placeholder="输入中文释义："
        />

        <template v-if="!answered">
          <div class="actions">
            <NButton type="primary" @click="onSubmit">提交</NButton>
          </div>
        </template>
        <template v-else>
          <NAlert :type="isCorrect ? 'success' : 'error'" show-icon class="feedback">
            <template v-if="isCorrect">✅ 正确！</template>
            <template v-else>
              ❌ 你的答案：{{ entry?.userAnswer }}　|　正确答案：<strong>{{ q.chinese }}</strong>
            </template>
          </NAlert>

          <div class="nav-row center">
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
.phon {
  color: #888;
  font-size: 14px;
}
.actions {
  margin-top: 16px;
}
.feedback {
  margin: 16px 0 12px;
}
.nav-row {
  display: flex;
  width: 100%;
}
.nav-row.center {
  justify-content: center;
}
</style>
