<script setup lang="ts">
// 中→英选择。源页 L822-868。英文干扰项来自 session 题集，进入该题时惰性生成、
// 按 word_id 缓存（prev/next 往返不重排）。答后揭示音标/词性/英释/例句（源 _phonetic_audio_inline）。
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
import { formatPhonetic } from '@/composables/usePhonetic'
import { genEnOptions } from '@/utils/practiceOptions'

const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)
const answered = computed(() => (q.value ? store.results.has(q.value.word_id) : false))
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)
const progressPct = computed(() =>
  store.total ? Math.round((store.idx / store.total) * 100) : 0,
)
const phonetic = computed(() => formatPhonetic(q.value?.phonetic))

const selected = ref<string | null>(null)
const enOptions = ref<string[]>([])
// 非响应式缓存：仅用于稳定每个词的干扰项排布，展示靠 enOptions ref 驱动。
const enOptionsCache = new Map<number, string[]>()

watch(
  () => q.value?.word_id,
  () => {
    const qv = q.value
    if (!qv) {
      selected.value = null
      enOptions.value = []
      return
    }
    selected.value = entry.value?.userAnswer ?? null
    let opts = enOptionsCache.get(qv.word_id)
    if (!opts) {
      opts = genEnOptions(qv, store.questions)
      enOptionsCache.set(qv.word_id, opts)
    }
    enOptions.value = opts
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
  const correct = selected.value === qv.english
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
        <h3 class="cn">{{ q.chinese }}</h3>

        <p class="opt-label">选择正确的英文：</p>
        <NRadioGroup v-model:value="selected" :disabled="answered">
          <div class="opt-list">
            <NRadio v-for="(opt, i) in enOptions" :key="i" :value="opt">{{ opt }}</NRadio>
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
              ❌ 你的答案：{{ entry?.userAnswer }}　|　正确答案：<strong>{{ q.english }}</strong>
            </template>
          </NAlert>

          <!-- 答后揭示：音标 + 播放 + 词性/英释 + 例句 -->
          <div class="reveal">
            <div class="reveal-line">
              <span v-if="phonetic" class="phon">{{ phonetic }}</span>
              <NButton size="small" quaternary @click="onPlay">🔊 播放</NButton>
            </div>
            <div v-if="q.pos || q.definition" class="meta">
              词性：{{ q.pos || '-' }}　·　英释：{{ q.definition || '-' }}
            </div>
            <div v-if="q.example" class="example">💬 {{ q.example }}</div>
          </div>

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
.cn {
  margin: 0 0 12px;
  font-size: 24px;
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
.reveal {
  margin-bottom: 12px;
}
.reveal-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.phon {
  font-size: 18px;
  color: #666;
}
.meta {
  color: #888;
  font-size: 13px;
  margin-top: 6px;
}
.example {
  margin-top: 6px;
  color: #444;
}
.nav-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
</style>
