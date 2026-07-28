<script setup lang="ts">
import { computed, watch, type Component } from 'vue'
import { NAlert, NButton, NPopconfirm, NProgress, NSelect, NSwitch } from 'naive-ui'

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

// TTS 播放速率（与 WordsView 一致；练习中可在顶栏实时调整）。
const SPEED_OPTIONS = [
  { label: '0.8×', value: 0.8 },
  { label: '1×', value: 1 },
  { label: '1.25×', value: 1.25 },
  { label: '1.5×', value: 1.5 },
]
function onSpeedChange(val: string | number | null): void {
  if (typeof val === 'number') store.fcSpeed = val
}

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
    <div v-if="phase === 'playing'" class="topbar">
      <span class="mode-tag">{{ modeLabel }}</span>
      <NProgress
        type="line"
        :percentage="progressPct"
        :show-indicator="true"
        class="topbar-prog"
      />
      <span class="prog-text">{{ store.idx + 1 }}/{{ store.total }}</span>
      <span class="audio-ctrl">
        <NSwitch v-model:value="store.autoPlay" size="small" />
        <span class="ctrl-label">🔊自动</span>
        <NSelect
          :value="store.fcSpeed"
          :options="SPEED_OPTIONS"
          size="small"
          style="width: 80px"
          @update:value="onSpeedChange"
        />
      </span>
      <NPopconfirm
        @positive-click="exitPractice"
        positive-text="确认"
        negative-text="取消"
      >
        <template #trigger>
          <NButton size="small" tertiary>
            {{ store.hasAnswer ? '结束并保存' : '退出(不记录)' }}
          </NButton>
        </template>
        {{ store.hasAnswer ? '确认结束并保存本次练习？' : '确认退出？本次进度不会记录。' }}
      </NPopconfirm>
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
      <PracticeSummary v-if="phase === 'done'" />
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 12px;
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
  font-size: 15px;
  color: #555;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.audio-ctrl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ctrl-label {
  font-size: 12px;
  color: #888;
  white-space: nowrap;
}
/* 窄屏：收起音频控件的文字标签，避免挤占顶栏 / 顶栏换行后过宽 */
@media (max-width: 480px) {
  .ctrl-label {
    display: none;
  }
  .audio-ctrl {
    flex-wrap: wrap;
  }
}
.retry-banner {
  margin-bottom: 12px;
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
