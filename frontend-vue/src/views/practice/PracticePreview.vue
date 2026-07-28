<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NButton, NEmpty, NSpace, NSpin } from 'naive-ui'

import { api } from '@/api/client'
import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'
import type { Word } from '@/api/types'

// 试听预览：拉所选 Unit 全部单词逐张浏览（英文+音标+中文+发音+富字段），不建 session、不计统计。
// 复用练习偏好（autoPlay/fcAutoNext/fcDelay/fcSpeed）；本地 idx 不碰 store.idx，避免污染 session。
// 错题本(0) 不支持预览（WrongWordItem 结构不同），由调用方过滤后传入 unit id(>0)。
const props = defineProps<{ unitIds: number[] }>()
const emit = defineEmits<{ exit: [] }>()

const store = usePracticeStore()
const { play } = useTtsAudio()

const words = ref<Word[]>([])
const loading = ref(true)
const idx = ref(0)
const cur = computed(() => words.value[idx.value] ?? null)
const phonetic = computed(() => (cur.value ? formatPhonetic(cur.value.phonetic) : ''))
const isLast = computed(() => idx.value >= words.value.length - 1)

let autoTimer: number | null = null
function clearAuto() {
  if (autoTimer !== null) {
    window.clearTimeout(autoTimer)
    autoTimer = null
  }
}

// 进入新词：自动播放（受 store.autoPlay）+ 自动下一张倒计时（受 store.fcAutoNext）。
watch(
  () => idx.value,
  () => {
    clearAuto()
    if (!cur.value) return
    if (store.autoPlay) void play(cur.value.english, store.fcSpeed)
    if (store.fcAutoNext) {
      autoTimer = window.setTimeout(() => goNext(), Math.max(0.5, store.fcDelay) * 1000)
    }
  },
  { immediate: true },
)

function playCur() {
  if (cur.value) void play(cur.value.english, store.fcSpeed)
}
function goPrev() {
  if (idx.value > 0) idx.value -= 1
}
function goNext() {
  if (idx.value < words.value.length - 1) idx.value += 1
}

const loadError = ref(false)

async function load() {
  loading.value = true
  loadError.value = false
  const all: Word[] = []
  let failed = 0
  for (const uid of props.unitIds) {
    if (uid <= 0) continue
    const r = await api.listWords(uid, 1, 2000)
    if (r.code === 200) all.push(...r.data.items)
    else failed += 1
  }
  words.value = all
  idx.value = 0
  // 全部 Unit 都拉失败且无词 → 错误态（区别于"所选 Unit 无单词"真空态）
  if (!all.length && failed) loadError.value = true
  loading.value = false
}

onMounted(load)
onBeforeUnmount(clearAuto)
</script>

<template>
  <div class="preview">
    <div class="preview-head">
      <span class="title">👀 试听预览</span>
      <span class="count">{{ words.length ? `${idx + 1} / ${words.length}` : '' }}</span>
      <NButton size="small" tertiary @click="emit('exit')">✖ 退出预览</NButton>
    </div>

    <NSpin v-if="loading" />
    <NEmpty v-else-if="loadError" description="加载失败">
      <template #extra>
        <NButton size="small" @click="load">重试</NButton>
      </template>
    </NEmpty>
    <NEmpty v-else-if="!words.length" description="所选 Unit 无单词" />
    <div v-else-if="cur" class="card">
      <div class="word-line">
        <span class="word">{{ cur.english }}</span>
        <span v-if="phonetic" class="phon">{{ phonetic }}</span>
        <NButton size="small" quaternary circle @click="playCur">🔊</NButton>
      </div>
      <div class="cn">{{ cur.chinese }}</div>
      <div v-if="cur.pos || cur.definition || cur.example" class="rich">
        <p v-if="cur.pos || cur.definition" class="meta">
          词性：{{ cur.pos || '-' }}　·　英释：{{ cur.definition || '-' }}
        </p>
        <p v-if="cur.example" class="example">💬 {{ cur.example }}</p>
      </div>

      <NSpace :size="12" class="nav">
        <NButton :disabled="idx === 0" @click="goPrev">⬅️ 上一张</NButton>
        <NButton v-if="!isLast" type="primary" @click="goNext">➡️ 下一张</NButton>
        <NButton v-else type="primary" @click="emit('exit')">✅ 看完了</NButton>
      </NSpace>
      <p class="hint">不计入统计。自动播放 / 自动下一题 / 速率沿用上方练习设置。</p>
    </div>
  </div>
</template>

<style scoped>
.preview {
  max-width: 640px;
  margin: 0 auto;
}
.preview-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.title {
  font-weight: 600;
  font-size: 18px;
}
.count {
  color: #888;
  font-size: 14px;
  flex: 1;
}
.card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
}
.word-line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.word {
  font-size: 30px;
  font-weight: 700;
}
.phon {
  color: #888;
  font-size: 17px;
}
.cn {
  font-size: 20px;
  font-weight: 600;
}
.rich {
  color: #555;
  font-size: 14px;
  line-height: 1.7;
}
.rich p {
  margin: 0;
}
.nav {
  margin-top: 4px;
}
.hint {
  color: #999;
  font-size: 12px;
  margin: 4px 0 0;
}
</style>
