<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { NAlert, NButton, NEmpty, NInput, NSpace, useMessage } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'

// 听写（源页 L930-963）。compact：题面只给音频 + caption，不显英文/中文；
// 答后揭示英文 + 音标 + 富字段（词性/英释/例句）。音频走 blob 缓存（零网络回放）。
const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)

const answer = ref('')
const inputRef = ref<InstanceType<typeof NInput> | null>(null)
const submitted = ref(false)
const skipped = ref(false)
// 提交给服务端的 userAnswer：dictation 用原始未 strip 的输入（与源页 L944-945 一致）；
// 跳过时为 ''。展示用 skipped ? '(跳过)' : userAnswer（与源页 L950/L958 一致）。
const userAnswer = ref('')

// 判定以服务端为准（store.results）：客户端先写乐观值，服务端 _norm 复判（剥非字母数字）后
// 自动纠正——避免输入「apple.」客户端判错而服务端判对造成的假 ❌ 反馈。
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)

const isLast = computed(() => store.idx >= store.total - 1)
const phoneticDisplay = computed(() => formatPhonetic(q.value?.phonetic))

// 进入新题：重置本地态并自动播放音频（compact，仅音频不显文字）。
watch(
  () => store.idx,
  () => {
    answer.value = ''
    submitted.value = false
    skipped.value = false
    userAnswer.value = ''
    const cur = store.currentQuestion
    if (cur && store.autoPlay) void play(cur.english, store.fcSpeed)
    // 进入新题自动聚焦输入框，便于连续「回车提交」
    if (!submitted.value) nextTick(() => inputRef.value?.focus())
  },
  { immediate: true },
)

function replay() {
  const cur = store.currentQuestion
  if (cur) void play(cur.english, store.fcSpeed)
}

function onSubmit() {
  if (submitted.value) return
  const cur = store.currentQuestion
  if (!cur) return
  const ans = answer.value
  // 空提交拦截（口径与 SpellingMode 一致）：不进入判分、不写后端，避免污染正确率/掌握度
  if (!ans.trim()) {
    message.warning('请输入答案后再提交')
    return
  }
  const correct = ans.trim().toLowerCase() === cur.english.toLowerCase()
  submitted.value = true
  skipped.value = false
  userAnswer.value = ans
  void store.submitOne(cur.word_id, correct, ans)
}

function onSkip() {
  if (submitted.value) return
  const cur = store.currentQuestion
  if (!cur) return
  submitted.value = true
  skipped.value = true
  userAnswer.value = ''
  void store.submitOne(cur.word_id, false, '')
}

function goNext() {
  store.setIdx(isLast.value ? store.total : store.idx + 1)
}
</script>

<template>
  <div v-if="q" class="dictation-mode">
    <p class="caption">🎧 听音频，拼写对应的英文单词</p>

    <NButton size="large" @click="replay">🔊 {{ submitted ? '再听' : '播放发音' }}</NButton>

    <NInput
      ref="inputRef"
      v-model:value="answer"
      placeholder="输入英文（回车提交）"
      :disabled="submitted"
      class="input"
      @keyup.enter="onSubmit"
    />

    <NSpace v-if="!submitted" :size="12">
      <NButton type="primary" @click="onSubmit">✅ 提交</NButton>
      <NButton @click="onSkip">⏭ 跳过</NButton>
    </NSpace>

    <div v-if="submitted" class="reveal">
      <NAlert :type="isCorrect ? 'success' : 'error'">
        <span v-if="isCorrect">✅ 正确！</span>
        <span v-else>
          ❌ 你的答案: {{ skipped ? '(跳过)' : userAnswer }}　|　正确答案: <b>{{ q.english }}</b>
        </span>
      </NAlert>

      <div class="word-line">
        <span class="word">{{ q.english }}</span>
        <span v-if="phoneticDisplay" class="phonetic">{{ phoneticDisplay }}</span>
        <NButton size="small" quaternary circle @click="replay">🔊</NButton>
      </div>

      <div v-if="q.pos || q.definition || q.example" class="rich">
        <p v-if="q.pos || q.definition" class="rich-meta">
          词性：{{ q.pos || '-' }}　·　英释：{{ q.definition || '-' }}
        </p>
        <p v-if="q.example" class="rich-example">💬 {{ q.example }}</p>
      </div>

      <NButton type="primary" @click="goNext">
        {{ isLast ? '✅ 完成练习' : '➡️ 下一题' }}
      </NButton>
    </div>
  </div>
  <NEmpty v-else description="暂无题目" />
</template>

<style scoped>
.dictation-mode {
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}
.caption {
  color: #6B7280;
  font-size: 14px;
  margin: 0;
}
.input {
  max-width: 360px;
}
.reveal {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
}
.word-line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.word {
  font-size: 22px;
  font-weight: 700;
}
.phonetic {
  color: #6B7280;
  font-size: 15px;
}
.rich {
  color: #555;
  font-size: 14px;
  line-height: 1.7;
  width: 100%;
}
.rich p {
  margin: 0;
}
</style>
