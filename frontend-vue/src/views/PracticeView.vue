<script setup lang="ts">
import { computed, watch, type Component } from 'vue'
import { NAlert, NButton, NProgress } from 'naive-ui'

import { modeMeta } from '@/constants/modes'
import { usePracticeStore } from '@/stores/practice'
import ChoiceMode from '@/views/practice/modes/ChoiceMode.vue'
import Cn2EnChoiceMode from '@/views/practice/modes/Cn2EnChoiceMode.vue'
import DictationMode from '@/views/practice/modes/DictationMode.vue'
import En2CnWriteMode from '@/views/practice/modes/En2CnWriteMode.vue'
import FlashcardMode from '@/views/practice/modes/FlashcardMode.vue'
import FlipMatchMode from '@/views/practice/modes/FlipMatchMode.vue'
import MatchingMode from '@/views/practice/modes/MatchingMode.vue'
import MemoryFlashMode from '@/views/practice/modes/MemoryFlashMode.vue'
import ScrambleMode from '@/views/practice/modes/ScrambleMode.vue'
import SpellingMode from '@/views/practice/modes/SpellingMode.vue'
import TimedChallengeMode from '@/views/practice/modes/TimedChallengeMode.vue'
import PracticeConfig from '@/views/practice/PracticeConfig.vue'
import PracticeSummary from '@/views/practice/PracticeSummary.vue'

const store = usePracticeStore()

const MODE_COMPS: Record<string, Component> = {
  flashcard: FlashcardMode,
  choice: ChoiceMode,
  cn2en_choice: Cn2EnChoiceMode,
  spelling: SpellingMode,
  en2cn_write: En2CnWriteMode,
  dictation: DictationMode,
  matching: MatchingMode,
  timed_challenge: TimedChallengeMode,
  scramble: ScrambleMode,
  memory_flash: MemoryFlashMode,
  flip_match: FlipMatchMode,
}

const modeComp = computed(() => MODE_COMPS[store.mode] ?? null)

watch(
  () => store.isDone,
  async (done) => {
    if (done) await store.finish()
  },
)

const phase = computed<'config' | 'playing' | 'done'>(() => {
  if (store.questions.length === 0) return 'config'
  if (store.isDone) return 'done'
  return 'playing'
})

const progressPct = computed(() => (store.total ? Math.round((store.idx / store.total) * 100) : 0))
const modeLabel = computed(() => modeMeta(store.mode)?.label ?? store.mode)

function exitPractice() {
  // 无答案→直接丢弃；有答案→推到末位触发 done→finish 保存
  if (!store.hasAnswer) store.restart()
  else store.setIdx(store.total)
}
</script>

<template>
  <div>
    <!-- 顶栏：进度 + 退出 -->
    <div v-if="phase !== 'config'" class="topbar">
      <span class="mode-tag">{{ modeLabel }}</span>
      <NProgress
        type="line"
        :percentage="progressPct"
        :show-indicator="false"
        class="topbar-prog"
      />
      <span class="prog-text">{{ store.idx }}/{{ store.total }}</span>
      <NButton size="small" tertiary @click="exitPractice">
        {{ store.hasAnswer ? '结束并保存' : '退出(不记录)' }}
      </NButton>
    </div>

    <PracticeConfig v-if="phase === 'config'" />
    <div v-else class="stage">
      <!-- 提交失败重试横幅 -->
      <NAlert v-if="store.submitFailures.length" type="error" class="retry-banner">
        <span>⚠️ 有 {{ store.submitFailures.length }} 次答题提交失败（已本地记录，后端幂等可重试）。</span>
        <div class="retry-actions">
          <NButton size="small" type="primary" @click="store.retryAllSubmits()">🔄 重试全部</NButton>
          <NButton size="small" @click="store.clearSubmits()">🗑️ 忽略</NButton>
        </div>
      </NAlert>

      <component :is="modeComp" v-if="phase === 'playing' && modeComp" />
      <PracticeSummary v-else-if="phase === 'done'" />
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  position: sticky;
  top: 0;
  background: var(--app-bg);
  padding: 6px 0;
  z-index: 5;
}
.mode-tag {
  font-weight: 600;
  white-space: nowrap;
}
.topbar-prog {
  flex: 1;
  min-width: 120px;
}
.prog-text {
  font-size: 13px;
  color: #888;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.retry-banner {
  margin-bottom: 16px;
}
.retry-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.stage {
  max-width: 860px;
  margin: 0 auto;
}
</style>
