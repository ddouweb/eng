<script setup lang="ts">
// 中→英拼写。源页 L871-900。大小写不敏感；提交前校验非空（源 L883）。
// 答后揭示音标/词性/英释/例句（源 _phonetic_audio_inline）。源页无「上一题」。
import { computed, ref, watch } from 'vue'
import { NAlert, NButton, NCard, NInput, useMessage } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'

const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)
const answered = computed(() => (q.value ? store.results.has(q.value.word_id) : false))
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)
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
  if (q.value) void play(q.value.english, store.fcSpeed)
}

async function onSubmit() {
  const qv = q.value
  if (!qv) return
  const ans = answer.value.trim()
  if (!ans) {
    message.warning('请输入答案后再提交')
    return
  }
  const correct = ans.toLowerCase() === qv.english.toLowerCase()
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
      <div v-if="q" class="body">
        <p class="cn"><strong>中文：</strong>{{ q.chinese }}</p>

        <NInput
          v-model:value="answer"
          :disabled="answered"
          placeholder="输入英文拼写："
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
              ❌ 你的拼写：{{ entry?.userAnswer }}　|　正确答案：<strong>{{ q.english }}</strong>
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
  margin: 0 auto;
}
.cn {
  font-size: 18px;
  margin: 0 0 12px;
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
  width: 100%;
}
.nav-row.center {
  justify-content: center;
}
</style>
