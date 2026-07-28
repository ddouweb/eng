<script setup lang="ts">
// 英→中选择。源页 L774-819。服务端预生成 q.options，前端只读。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NAlert, NButton, NCard, useMessage } from 'naive-ui'

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
const options = computed(() => {
  const qv = q.value
  if (!qv) return [] as string[]
  return qv.options && qv.options.length ? qv.options : [qv.chinese]
})
const phonetic = computed(() => formatPhonetic(q.value?.phonetic))

const selected = ref<string | null>(null)
// 上一题回访时从 store.results 复原所选；进入新题清空。
watch(
  () => q.value?.word_id,
  () => {
    selected.value = entry.value?.userAnswer ?? null
  },
  { immediate: true },
)

function selectOption(opt: string) {
  if (answered.value) return
  selected.value = opt
}

// 选项级对错反馈：正确答案恒绿；用户选错的选项红；未选的正确答案也高亮
function optionStatus(opt: string): 'correct' | 'wrong' | null {
  if (!answered.value || !q.value) return null
  if (opt === q.value.chinese) return 'correct'
  if (opt === selected.value) return 'wrong'
  return null
}

function optionClass(opt: string) {
  const status = optionStatus(opt)
  return {
    'is-selected': !answered.value && selected.value === opt,
    'is-correct': status === 'correct',
    'is-wrong': status === 'wrong',
  }
}

function optionMark(opt: string) {
  const s = optionStatus(opt)
  if (s === 'correct') return '✓'
  if (s === 'wrong') return '✗'
  return ''
}

function onPlay() {
  if (q.value) void play(q.value.english, store.fcSpeed)
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

// 数字键 1-9 选择对应选项，回车确认提交（未答时生效）
function onKeydown(e: KeyboardEvent) {
  if (answered.value || !q.value) return
  const n = Number(e.key)
  if (Number.isInteger(n) && n >= 1 && n <= options.value.length) {
    selected.value = options.value[n - 1]
    e.preventDefault()
    return
  }
  if (e.key === 'Enter') {
    void onSubmit()
    e.preventDefault()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="mode-wrap">
    <NCard size="medium">
      <div v-if="q" class="body">
        <div class="word-line">
          <span class="word">{{ q.english }}</span>
          <span v-if="phonetic" class="phon">{{ phonetic }}</span>
          <NButton size="small" quaternary @click="onPlay">🔊 播放</NButton>
        </div>

        <p class="opt-label">
          选择正确的中文释义：<span class="opt-hint">数字键选择，回车确认</span>
        </p>
        <div class="opt-list">
          <button
            v-for="(opt, i) in options"
            :key="opt"
            type="button"
            class="opt"
            :class="optionClass(opt)"
            :disabled="answered"
            @click="selectOption(opt)"
          >
            <span class="opt-key">{{ i + 1 }}</span>
            <span class="opt-text">{{ opt }}</span>
            <span v-if="optionMark(opt)" class="opt-mark">{{ optionMark(opt) }}</span>
          </button>
        </div>

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
  margin: 0 auto;
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
  color: #6B7280;
  font-size: 15px;
}
.opt-label {
  margin: 0 0 8px;
  color: #555;
}
.opt-hint {
  color: #6B7280;
  font-size: 12px;
  margin-left: 4px;
}
.opt-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.opt {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 11px 14px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
  color: #1f2329;
  font-size: 15px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.opt:hover:not(:disabled) {
  border-color: #18a058;
}
.opt.is-selected {
  border-color: #18a058;
  background: rgba(24, 160, 88, 0.06);
}
.opt.is-correct {
  border-color: #18a058;
  background: rgba(24, 160, 88, 0.12);
  color: #18a058;
  font-weight: 600;
}
.opt.is-wrong {
  border-color: #d03050;
  background: rgba(208, 48, 80, 0.1);
  color: #d03050;
  font-weight: 600;
}
.opt:disabled {
  cursor: default;
}
.opt-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: #f0f2f5;
  color: #6B7280;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.opt-text {
  flex: 1;
  word-break: break-word;
}
.opt-mark {
  margin-left: auto;
  font-weight: 700;
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
