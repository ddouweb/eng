<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { NButton, NProgress, NTag } from 'naive-ui'

import { usePracticeStore } from '@/stores/practice'
import { useTtsAudio } from '@/composables/useTtsAudio'
import { formatPhonetic } from '@/composables/usePhonetic'
import { masteryMeta } from '@/constants/mastery'
import { tagMeta, type TagMeta } from '@/constants/tags'

// 单词卡（源页 L650-771）。双路：
//  - auto（store.fcAutoNext）：点认识/不认识 → 立即 submitOne → 揭示中文 → 倒计时 fcDelay 秒自动下一题，
//    期间可手动「下一题」clearTimeout 抢先。
//  - manual：点按钮只置 pending（可反复改），「下一题」时才 submitOne + setIdx+1。
// 认识 → isCorrect=true / userAnswer=null；不认识 → isCorrect=false / userAnswer=english。
//
// 重设计（扁平卡片，对齐参考图）：不做翻转，所有信息平铺。
//  - 未答：单词+音标+播放 + 「显示答案」(peek 偷看释义，不等于作答) + 认识/不认识。
//  - 已答：浅蓝释义卡 + 英文释义/例句/态势徽章 + auto 倒计时耗尽条 / manual 改判 + 下一题。
// behavior 函数（onAnswer/goNext/togglePending/confirmManualNext/startAutoCountdown/clearTimers/watch/
// onBeforeUnmount）逐行保留，仅新增只读展示。
const store = usePracticeStore()
const { play } = useTtsAudio()

const q = computed(() => store.currentQuestion)

const answered = ref(false)
// 答前「显示答案」（偷看中文释义，不等于作答；对齐老版 fc_show）。
const peeked = ref(false)
// manual 路径下的待定判定：true=认识 / false=不认识 / null=未选。
const pending = ref<boolean | null>(null)
// auto 路径倒计时剩余秒数（用于耗尽进度条 + 文案展示）。
const autoRemaining = ref(0)
// 本题是否已前进（防 auto 倒计时到点与手动「下一题」竞态导致跳两题）。
const advanced = ref(false)

// 真 setTimeout/setInterval 句柄，onBeforeUnmount 与 goNext 必须清理（铁律）。
// 用 window.* 走 DOM 签名（返回 number），规避 @types/node 的 NodeJS.Timeout 歧义。
let displayTimer: number | null = null
let advanceTimer: number | null = null

const isLast = computed(() => store.idx >= store.total - 1)
const phoneticDisplay = computed(() => formatPhonetic(q.value?.phonetic))

// ── 只读派生：不引入可写状态、不调任何 API ──
// 掌握度元信息：masteryMeta 对 null/undefined 兜底为 unlearned，永远返回 {label,emoji,color}。
const masteryInfo = computed(() => masteryMeta(q.value?.mastery_level))
const displayTags = computed<TagMeta[]>(() =>
  (q.value?.tags ?? []).map((t) => tagMeta(t)).filter((m): m is TagMeta => !!m),
)
// 句子型（type==='sentence'）：english 本身是例句 → 缩主词字号、隐藏词性与「例句」区避免重复。
const isSentence = computed(() => q.value?.type === 'sentence')
// auto 倒计时耗尽进度条：100% → 0%；delay<=0 时恒 0（除零兜底）。
const countdownPct = computed(() => {
  const d = store.fcDelay
  return d > 0 ? Math.max(0, Math.min(100, (autoRemaining.value / d) * 100)) : 0
})

function clearTimers() {
  if (displayTimer !== null) {
    window.clearInterval(displayTimer)
    displayTimer = null
  }
  if (advanceTimer !== null) {
    window.clearTimeout(advanceTimer)
    advanceTimer = null
  }
}

function goNext() {
  if (advanced.value) return
  advanced.value = true
  clearTimers()
  store.setIdx(isLast.value ? store.total : store.idx + 1)
}

// auto 路径：答后启动倒计时；到点自动下一题。displayTimer 每 100ms 刷新剩余秒数展示。
function startAutoCountdown() {
  clearTimers()
  const delaySec = Math.max(0, store.fcDelay)
  const start = Date.now()
  autoRemaining.value = delaySec
  displayTimer = window.setInterval(() => {
    const elapsed = (Date.now() - start) / 1000
    autoRemaining.value = Math.max(0, delaySec - elapsed)
  }, 100)
  advanceTimer = window.setTimeout(() => {
    goNext()
  }, delaySec * 1000)
}

function replay() {
  const cur = store.currentQuestion
  if (cur) void play(cur.english, store.fcSpeed)
}

function onAnswer(recognized: boolean) {
  const cur = store.currentQuestion
  if (!cur || answered.value) return
  answered.value = true
  if (store.fcAutoNext) {
    // auto：立即提交，揭示中文，启动倒计时。
    void store.submitOne(cur.word_id, recognized, recognized ? null : cur.english)
    startAutoCountdown()
  } else {
    // manual：仅置 pending，可反复改，下一题时才提交。
    pending.value = recognized
  }
}

function togglePending(recognized: boolean) {
  if (answered.value && !store.fcAutoNext) {
    pending.value = recognized
  }
}

function confirmManualNext() {
  if (!answered.value || store.fcAutoNext) return
  const rec = pending.value
  if (rec === null) return
  const cur = store.currentQuestion
  if (!cur) return
  void store.submitOne(cur.word_id, rec, rec ? null : cur.english)
  goNext()
}

// 进入新题：清旧定时器 + 重置本地态 + 自动播放音频。
// answered/peeked 归零 → 释义卡与揭示区收起，回到未答状态。
watch(
  () => store.idx,
  () => {
    clearTimers()
    answered.value = false
    peeked.value = false
    pending.value = null
    autoRemaining.value = 0
    advanced.value = false
    const cur = store.currentQuestion
    if (cur && store.autoPlay) void play(cur.english, store.fcSpeed)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <div v-if="q" class="flashcard-mode">
    <div class="fc-card" :class="{ 'is-sentence': isSentence }">
      <!-- 顶部掌握度色条（随 mastery 染色，一眼看熟度） -->
      <div class="fc-accent" :style="{ background: masteryInfo.color }"></div>

      <div class="fc-body">
        <!-- 顶部：左=单词+音标(+词性)，右=播放 -->
        <div class="fc-head">
          <div class="fc-word-block">
            <div class="fc-word">{{ q.english }}</div>
            <div class="fc-sub">
              <span v-if="phoneticDisplay" class="fc-phonetic">{{ phoneticDisplay }}</span>
              <span v-if="q.pos && !isSentence" class="fc-pos">{{ q.pos }}</span>
            </div>
          </div>
          <NButton class="fc-play" quaternary circle size="large" @click="replay">🔊</NButton>
        </div>

        <!-- 元信息：掌握度 pill + 标签（次级灰，不抢色） -->
        <div v-if="q.mastery_level || displayTags.length" class="fc-meta">
          <span v-if="q.mastery_level" class="fc-mastery" :style="{ color: masteryInfo.color }">
            <i class="fc-dot" :style="{ background: masteryInfo.color }"></i>{{ masteryInfo.label }}
          </span>
          <NTag
            v-for="t in displayTags"
            :key="t.value"
            size="small"
            round
            :bordered="false"
          >{{ t.emoji }} {{ t.label }}</NTag>
        </div>

        <!-- 显示/隐藏答案（peek，不等于作答） -->
        <div v-if="!answered" class="fc-toggle-answer">
          <NButton size="small" tertiary @click="peeked = !peeked">
            {{ peeked ? '🙈 隐藏答案' : '👁 显示答案' }}
          </NButton>
        </div>

        <!-- 中文释义卡（浅蓝高亮；peek 或已答时显示） -->
        <Transition name="fc-fade">
          <div v-if="peeked || answered" class="fc-answer-card">
            <div class="fc-answer-text">{{ q.chinese }}</div>
          </div>
        </Transition>

        <!-- 已答后的补充信息：英文释义 / 例句 / 态势徽章 -->
        <Transition name="fc-fade">
          <div v-if="answered" class="fc-reveal">
            <div v-if="q.definition" class="fc-section">
              <div class="fc-section-title">英文释义</div>
              <div class="fc-section-body">{{ q.definition }}</div>
            </div>
            <div v-if="q.example && !isSentence" class="fc-section">
              <div class="fc-section-title">例句</div>
              <blockquote class="fc-example">{{ q.example }}</blockquote>
            </div>
            <div
              v-if="q.is_new || q.is_due || (q.wrong_count ?? 0) > 0"
              class="fc-stats"
            >
              <span v-if="q.is_new" class="fc-chip">🆕 新词</span>
              <span v-if="q.is_due" class="fc-chip">
                ⏰ 到期<template v-if="(q.overdue_days ?? 0) > 0"> · 逾期{{ q.overdue_days }}天</template>
              </span>
              <span v-if="(q.wrong_count ?? 0) > 0" class="fc-chip">⚠️ 错{{ q.wrong_count }}次</span>
            </div>
          </div>
        </Transition>

        <!-- 答题按钮（未答）：白底灰边 + 绿/红文字图标，对齐参考图 -->
        <div v-if="!answered" class="fc-actions">
          <NButton size="large" class="fc-btn-know" @click="onAnswer(true)">
            <span class="fc-btn-text">✓ 认识</span>
          </NButton>
          <NButton size="large" class="fc-btn-dont" @click="onAnswer(false)">
            <span class="fc-btn-text">✗ 不认识</span>
          </NButton>
        </div>

        <!-- 已答底部：auto 倒计时耗尽条 / manual 改判 + 下一题 -->
        <div v-if="answered" class="fc-footer">
          <template v-if="store.fcAutoNext">
            <div class="fc-countdown-caption">⏱️ {{ autoRemaining.toFixed(1) }}s 后自动下一题</div>
            <NProgress
              class="fc-countdown-bar"
              status="success"
              :percentage="countdownPct"
              :show-indicator="false"
              :height="6"
              :border-radius="3"
            />
            <NButton type="primary" size="large" @click="goNext">➡️ 下一题</NButton>
          </template>
          <template v-else>
            <div class="fc-manual-hint">可在下一题前改判</div>
            <div class="fc-toggle">
              <NButton
                :type="pending === true ? 'primary' : 'default'"
                @click="togglePending(true)"
              >{{ pending === true ? '✓ 已标记：认识' : '✓ 认识' }}</NButton>
              <NButton
                :type="pending === false ? 'primary' : 'default'"
                @click="togglePending(false)"
              >{{ pending === false ? '✗ 已标记：不认识' : '✗ 不认识' }}</NButton>
            </div>
            <NButton type="primary" size="large" :disabled="pending === null" @click="confirmManualNext">
              ➡️ 下一题
            </NButton>
          </template>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="empty">暂无题目</div>
</template>

<style scoped>
.flashcard-mode {
  display: flex;
  justify-content: center;
}

/* 卡片：扁平、不翻转；overflow 仅裁顶部色条圆角 */
.fc-card {
  width: 100%;
  max-width: 600px;
  position: relative;
  background: #fff;
  border: 1px solid #e6e8eb;
  border-radius: 16px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.fc-accent {
  height: 4px;
  width: 100%;
}
.fc-body {
  padding: 24px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 顶部：单词+音标 / 播放 */
.fc-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.fc-word-block {
  min-width: 0;
}
.fc-word {
  font-size: clamp(28px, 6vw, 34px);
  font-weight: 700;
  color: #1f2329;
  letter-spacing: -0.01em;
  word-break: break-word;
  line-height: 1.2;
}
/* 句子型：缩字号 */
.fc-card.is-sentence .fc-word {
  font-size: clamp(20px, 4.5vw, 26px);
}
.fc-sub {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fc-phonetic {
  font-size: 18px;
  color: #666;
}
.fc-pos {
  font-size: 13px;
  color: #888;
  border: 1px solid #e0e0e0;
  border-radius: 999px;
  padding: 1px 9px;
}
.fc-play {
  flex-shrink: 0;
}

/* 元信息 */
.fc-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.fc-mastery {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
}
.fc-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

/* 显示/隐藏答案 */
.fc-toggle-answer {
  display: flex;
}

/* 中文释义卡：浅蓝高亮（对齐参考图） */
.fc-answer-card {
  background: #f0f8ff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 16px 18px;
}
.fc-answer-text {
  font-size: clamp(20px, 4.5vw, 24px);
  font-weight: 600;
  color: #1f4d99;
  word-break: break-word;
  line-height: 1.4;
}

/* 已答补充信息 */
.fc-reveal {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fc-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #888;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.fc-section-body {
  font-size: 15px;
  color: #666;
  line-height: 1.5;
}
.fc-example {
  margin: 0;
  padding-left: 12px;
  border-left: 3px solid #18a058;
  font-size: 15px;
  color: #555;
  font-style: italic;
  line-height: 1.5;
}
.fc-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.fc-chip {
  font-size: 12px;
  color: #666;
  background: #f0f2f5;
  border-radius: 6px;
  padding: 3px 8px;
}

/* 答题按钮：白底灰边 + 绿/红文字图标 */
.fc-actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
.fc-actions :deep(.n-button) {
  flex: 1;
}
.fc-btn-know .fc-btn-text {
  color: #18a058;
  font-weight: 600;
  font-size: 17px;
}
.fc-btn-dont .fc-btn-text {
  color: #d03050;
  font-weight: 600;
  font-size: 17px;
}

/* 已答底部 */
.fc-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fc-countdown-caption {
  font-size: 12px;
  color: #888;
  text-align: center;
}
.fc-manual-hint {
  font-size: 12px;
  color: #999;
  text-align: center;
}
.fc-toggle {
  display: flex;
  gap: 10px;
}
.fc-toggle :deep(.n-button) {
  flex: 1;
}

/* 释义卡 / 揭示区淡入 */
.fc-fade-enter-active,
.fc-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.fc-fade-enter-from,
.fc-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.empty {
  color: #999;
}

@media (max-width: 560px) {
  .fc-body {
    padding: 20px 16px 16px;
  }
}
</style>
