<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NProgress,
  NSpace,
} from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { shuffle } from '@/utils/practiceOptions'

// 翻牌寻配：BATCH=4 → 8 张牌（4 en + 4 cn），shuffle 后铺开，翻两张配对。
// 本模式自管 batch/cards 状态，判定经 store.submitOne，
// batch 边界 store.setIdx，全部完成 store.setIdx(total)。
interface FlipCard {
  wid: number
  text: string
  en: boolean
}

const store = usePracticeStore()
const BATCH = 4

const cards = ref<FlipCard[]>([])
const flipped = ref<number[]>([])
const matched = ref<Set<number>>(new Set())
const attempts = ref(0)
const batch = ref(0)
const mismatch = ref(false)
const mmCards = ref<number[]>([])

let mmTimer: ReturnType<typeof setTimeout> | null = null

function buildCards(b: number): FlipCard[] {
  const qs = store.questions.slice(b * BATCH, b * BATCH + BATCH)
  const list: FlipCard[] = []
  for (const q of qs) {
    list.push({ wid: q.word_id, text: q.english, en: true })
    list.push({ wid: q.word_id, text: q.chinese, en: false })
  }
  return shuffle(list)
}

// 进度分母用对数（源 L1214：已配对对数 = 本批 matched//2 + 之前批 BATCH 累计）。
const pairsMatched = computed(
  () => Math.floor(matched.value.size / 2) + batch.value * BATCH,
)
const pct = computed(() =>
  store.total === 0 ? 0 : Math.round((pairsMatched.value / store.total) * 100),
)

function isFaceUp(idx: number): boolean {
  return (
    matched.value.has(idx) ||
    flipped.value.includes(idx) ||
    (mismatch.value && mmCards.value.includes(idx))
  )
}

function cardType(idx: number): 'default' | 'success' {
  return matched.value.has(idx) ? 'success' : 'default'
}

// 细粒度推进顶栏进度（store.idx）：本批起点 + 已配对对数。
// 仅最后一批全部配对才 = total → 触发 isDone，不提前结束。
function syncProgress(): void {
  store.setIdx(
    Math.min(batch.value * BATCH + Math.floor(matched.value.size / 2), store.total),
  )
}

async function onCard(idx: number): Promise<void> {
  if (mismatch.value) return
  if (flipped.value.length >= 2) return
  if (matched.value.has(idx)) return
  if (flipped.value.includes(idx)) return

  flipped.value = [...flipped.value, idx]
  if (flipped.value.length < 2) return

  // 翻满两张 → 判定
  attempts.value += 1
  const [i1, i2] = flipped.value
  const c1 = cards.value[i1]
  const c2 = cards.value[i2]
  flipped.value = []

  if (c1.wid === c2.wid && c1.en !== c2.en) {
    // 配对成功
    const m = new Set(matched.value)
    m.add(i1)
    m.add(i2)
    matched.value = m
    await store.submitOne(c1.wid, true, null)
    syncProgress()
    advanceIfBatchDone()
  } else {
    // 不匹配：闪现一帧后翻回
    mismatch.value = true
    mmCards.value = [i1, i2]
    if (mmTimer) clearTimeout(mmTimer)
    mmTimer = setTimeout(() => {
      mismatch.value = false
      mmCards.value = []
      mmTimer = null
    }, 800)
    await store.submitOne(c1.wid, false, c2.text)
  }
}

function advanceIfBatchDone(): void {
  if (cards.value.length === 0) return
  if (matched.value.size < cards.value.length) return
  // 当前批全部配对 → 下一批
  batch.value += 1
  const next = buildCards(batch.value)
  if (next.length === 0) {
    // 越界 → 全部完成（保留当前牌面，父页将切到结束视图）
    store.setIdx(store.total)
    return
  }
  cards.value = next
  matched.value = new Set()
  flipped.value = []
  mmCards.value = []
  attempts.value = 0
  store.setIdx(Math.min(batch.value * BATCH, store.total))
}

onMounted(() => {
  cards.value = buildCards(0)
})

onBeforeUnmount(() => {
  if (mmTimer) clearTimeout(mmTimer)
})
</script>

<template>
  <NCard>
    <NSpace vertical :size="12">
      <div class="fm-progress-text">
        第 {{ batch + 1 }} 轮 · 翻牌 {{ attempts }} 次
      </div>
      <NProgress :percentage="pct" :show-indicator="false" />
      <div v-if="mismatch" class="fm-mismatch">❌ 不匹配！再试试</div>
      <div class="fm-caption">🔍 翻两张牌，找到英文和中文的配对</div>
      <NGrid :cols="4" :x-gap="12" :y-gap="12">
        <NGridItem v-for="(c, idx) in cards" :key="`fm_${batch}_${idx}`">
          <NButton
            block
            size="large"
            :type="cardType(idx)"
            :disabled="isFaceUp(idx) || mismatch || flipped.length >= 2"
            class="fm-card"
            @click="onCard(idx)"
          >
            <span v-if="isFaceUp(idx)">{{ c.en ? '🇬🇧' : '🇨🇳' }} {{ c.text }}</span>
            <span v-else class="fm-back">🂠</span>
          </NButton>
        </NGridItem>
      </NGrid>
    </NSpace>
  </NCard>
</template>

<style scoped>
.fm-progress-text {
  font-weight: 600;
}
.fm-mismatch {
  color: #d03050;
  font-weight: 600;
}
.fm-caption {
  color: #999;
  font-size: 13px;
}
.fm-card {
  height: 72px;
  font-size: 15px;
}
.fm-back {
  font-size: 22px;
}
</style>
