<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert, NButton, NInput, NSpace, useMessage } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'
import { scramble } from '@/utils/practiceOptions'

// 打乱重排（源页 L1081-1115）。展示中文释义 + 打散字母；进入该题惰性生成、按 word_id 缓存。
// 判定：ans.trim().toLowerCase() === english.toLowerCase()；userAnswer = ans.trim()（已 strip）。
const store = usePracticeStore()
const message = useMessage()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)

const answer = ref('')
const submitted = ref(false)
const userAnswer = ref('')
const scrambled = ref('')

// 判定以服务端为准（store.results）：客户端先写乐观值，服务端 _norm 复判（剥撇号/连字符等
// 非字母数字）后自动纠正——避免漏输撇号（dont vs don't）客户端判错而服务端判对的假 ❌。
const entry = computed(() => (q.value ? store.results.get(q.value.word_id) : undefined))
const isCorrect = computed(() => entry.value?.isCorrect ?? false)

// 按 word_id 缓存打乱结果，避免同一题重入重新打乱（线性流程下复用机会少，契约要求）。
const scrambleCache = new Map<number, string>()

const isLast = computed(() => store.idx >= store.total - 1)
const phoneticDisplay = computed(() => formatPhonetic(q.value?.phonetic))

watch(
  () => store.idx,
  () => {
    const cur = store.currentQuestion
    if (cur) {
      let s = scrambleCache.get(cur.word_id)
      if (!s) {
        s = scramble(cur.english)
        scrambleCache.set(cur.word_id, s)
      }
      scrambled.value = s
    }
    answer.value = ''
    submitted.value = false
    userAnswer.value = ''
  },
  { immediate: true },
)

function replay() {
  const cur = store.currentQuestion
  if (cur) void play(cur.english)
}

function onSubmit() {
  if (submitted.value) return
  const cur = store.currentQuestion
  if (!cur) return
  const ans = answer.value.trim()
  if (!ans) {
    message.warning('请输入答案后再提交')
    return
  }
  const correct = ans.toLowerCase() === cur.english.toLowerCase()
  submitted.value = true
  userAnswer.value = ans
  void store.submitOne(cur.word_id, correct, ans)
}

function goNext() {
  store.setIdx(isLast.value ? store.total : store.idx + 1)
}
</script>

<template>
  <div v-if="q" class="scramble-mode">
    <p class="meaning"><b>中文释义：</b>{{ q.chinese }}</p>

    <div class="letter-tiles">
      <span v-for="(ch, i) in scrambled" :key="i" class="tile">{{ ch }}</span>
    </div>

    <p class="caption">将上面的字母重新排列成正确的英文单词</p>

    <NInput
      v-model:value="answer"
      placeholder="输入答案"
      :disabled="submitted"
      class="input"
      @keyup.enter="onSubmit"
    />

    <NSpace v-if="!submitted" :size="12">
      <NButton type="primary" @click="onSubmit">提交</NButton>
    </NSpace>

    <div v-if="submitted" class="reveal">
      <NAlert :type="isCorrect ? 'success' : 'error'">
        <span v-if="isCorrect">✅ 正确！</span>
        <span v-else>
          ❌ 你的答案: {{ userAnswer }}　|　正确答案: <b>{{ q.english }}</b>
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
  <div v-else class="empty">暂无题目</div>
</template>

<style scoped>
.scramble-mode {
  max-width: 640px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
}
.meaning {
  font-size: 16px;
  margin: 0;
}
.letter-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tile {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 44px;
  padding: 0 8px;
  border-radius: 8px;
  background: #f0f0f0;
  font-size: 22px;
  font-weight: 700;
  font-family: monospace;
}
.caption {
  color: #888;
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
  color: #888;
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
.empty {
  color: #999;
}
</style>
