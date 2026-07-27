<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NProgress,
  NSpace,
} from 'naive-ui'

import type { PracticeQuestion } from '@/api/types'
import { usePracticeStore } from '@/stores/practice'
import { shuffle } from '@/utils/practiceOptions'

// 连连看：左列英文（原序）与右列中文（每批 shuffle 一次）配对。BATCH=4。
// 本模式自管 batch 指针，读 store.questions / store.total；
// 判定经 store.submitOne，batch 边界 store.setIdx，全部完成 store.setIdx(total)。
const store = usePracticeStore()
const BATCH = 4

const batch = ref(0)
const matched = ref<Set<number>>(new Set())
const selEn = ref<number | null>(null)
const wrong = ref(0)
const mismatch = ref(false)
// 按 batch 缓存中文列顺序，避免重新打乱导致视觉跳变。
const cnOrderCache = ref<Map<number, number[]>>(new Map())

let mmTimer: ReturnType<typeof setTimeout> | null = null

const batchQs = computed<PracticeQuestion[]>(() =>
  store.questions.slice(batch.value * BATCH, batch.value * BATCH + BATCH),
)

const cnOrder = computed<number[]>(() => cnOrderCache.value.get(batch.value) ?? [])

const cnItems = computed<PracticeQuestion[]>(() =>
  cnOrder.value.map((i) => batchQs.value[i]),
)

// 已处理总数 = 当前批起点 + 本批已配对数（Streamlit 同口径 overall）。
const overall = computed(() => Math.min(store.idx + matched.value.size, store.total))
const pct = computed(() =>
  store.total === 0 ? 0 : Math.round((overall.value / store.total) * 100),
)

function ensureCnOrder(b: number): void {
  if (cnOrderCache.value.has(b)) return
  const qs = store.questions.slice(b * BATCH, b * BATCH + BATCH)
  cnOrderCache.value.set(b, shuffle(qs.map((_, i) => i)))
}

watch(batch, (b) => ensureCnOrder(b), { immediate: true })

function flashMismatch(): void {
  mismatch.value = true
  if (mmTimer) clearTimeout(mmTimer)
  mmTimer = setTimeout(() => {
    mismatch.value = false
    mmTimer = null
  }, 800)
}

function enLabel(q: PracticeQuestion): string {
  if (matched.value.has(q.word_id)) return `✅ ${q.english}`
  if (selEn.value === q.word_id) return `👉 ${q.english}`
  return q.english
}
function enDisabled(wid: number): boolean {
  return matched.value.has(wid) || selEn.value === wid
}
function enType(wid: number): 'default' | 'info' | 'success' {
  if (matched.value.has(wid)) return 'success'
  if (selEn.value === wid) return 'info'
  return 'default'
}
function cnLabel(q: PracticeQuestion): string {
  return matched.value.has(q.word_id) ? `✅ ${q.chinese}` : q.chinese
}
function cnDisabled(wid: number): boolean {
  return matched.value.has(wid)
}
function cnType(wid: number): 'default' | 'success' {
  return matched.value.has(wid) ? 'success' : 'default'
}

function onEn(wid: number): void {
  if (mismatch.value) return // 800ms 错配闪现期间锁输入，避免「报错又配对成功」的矛盾视觉（与 FlipMatchMode 一致）
  if (matched.value.has(wid)) return
  selEn.value = wid
}

async function onCn(q: PracticeQuestion): Promise<void> {
  if (mismatch.value) return
  const wid2 = q.word_id
  if (matched.value.has(wid2)) return
  if (selEn.value == null) return // 源页同口径：未选英文时点中文为静默 no-op
  const sel = selEn.value
  selEn.value = null
  if (sel === wid2) {
    const next = new Set(matched.value)
    next.add(sel)
    matched.value = next
    await store.submitOne(sel, true, null)
    syncProgress()
    advanceIfBatchDone()
  } else {
    wrong.value += 1
    flashMismatch()
    await store.submitOne(sel, false, q.english)
  }
}

// 细粒度推进顶栏进度（store.idx）：本批起点 + 本批已配对数（与 Streamlit overall 同口径）。
// 仅最后一批全部配对才 = total → 触发 isDone，不提前结束。
function syncProgress(): void {
  store.setIdx(Math.min(batch.value * BATCH + matched.value.size, store.total))
}

function advanceIfBatchDone(): void {
  const qs = batchQs.value
  if (qs.length === 0) {
    store.setIdx(store.total) // 越界 → done
    return
  }
  if (matched.value.size < qs.length) return
  // 当前批全部配对 → 推进
  batch.value += 1
  matched.value = new Set()
  selEn.value = null
  const newQs = batchQs.value
  if (newQs.length === 0) {
    store.setIdx(store.total) // 越界 → 全部完成
  } else {
    store.setIdx(Math.min(batch.value * BATCH, store.total))
  }
}

onBeforeUnmount(() => {
  if (mmTimer) clearTimeout(mmTimer)
})
</script>

<template>
  <NCard>
    <NSpace vertical :size="12">
      <div class="mg-progress-text">
        第 {{ batch + 1 }} 轮 · 已配对 {{ overall }}/{{ store.total
        }}<span v-if="wrong"> · 错配 {{ wrong }}</span>
      </div>
      <NProgress :percentage="pct" :show-indicator="false" />
      <div v-if="mismatch" class="mg-mismatch">❌ 不匹配！再试试</div>
      <div class="mg-caption">👉 先点左边英文，再点右边中文完成配对</div>
      <NGrid :cols="2" :x-gap="16" :y-gap="8">
        <NGridItem>
          <div class="mg-col-title">English</div>
          <NSpace vertical :size="8">
            <NButton
              v-for="q in batchQs"
              :key="`en_${q.word_id}`"
              block
              :type="enType(q.word_id)"
              :disabled="enDisabled(q.word_id)"
              @click="onEn(q.word_id)"
            >
              {{ enLabel(q) }}
            </NButton>
          </NSpace>
        </NGridItem>
        <NGridItem>
          <div class="mg-col-title">中文</div>
          <NSpace vertical :size="8">
            <NButton
              v-for="q in cnItems"
              :key="`cn_${q.word_id}`"
              block
              :type="cnType(q.word_id)"
              :disabled="cnDisabled(q.word_id)"
              @click="onCn(q)"
            >
              {{ cnLabel(q) }}
            </NButton>
          </NSpace>
        </NGridItem>
      </NGrid>
    </NSpace>
  </NCard>
</template>

<style scoped>
.mg-progress-text {
  font-weight: 600;
}
.mg-mismatch {
  color: #d03050;
  font-weight: 600;
}
.mg-caption {
  color: #999;
  font-size: 13px;
}
.mg-col-title {
  font-weight: 700;
  margin-bottom: 4px;
}
</style>
