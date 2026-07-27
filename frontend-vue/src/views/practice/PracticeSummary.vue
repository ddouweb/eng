<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import { NAlert, NButton, NCard, NProgress, NSpace, NStatistic, NTag, useMessage } from 'naive-ui'

import { api } from '@/api/client'
import { MASTERY_ORDER, masteryMeta } from '@/constants/mastery'
import { TAGS } from '@/constants/tags'
import { usePracticeStore } from '@/stores/practice'

const store = usePracticeStore()
const message = useMessage()

const stats = computed(() => {
  const total = store.finishData?.total_count ?? store.total
  const correct = store.finishData?.correct_count ?? store.localCorrect
  const acc = store.finishData?.accuracy ?? (total ? Math.round((correct / total) * 100) : 0)
  return { total, correct, acc }
})

function entryOf(wordId: number) {
  return store.results.get(wordId)
}
// 仅已作答的词才允许改判（未提交词后端无 record → 404，改判必失败）
function canRejudge(wordId: number) {
  return entryOf(wordId) != null
}

async function rejudge(wordId: number, target: boolean) {
  const ok = await store.rejudge(wordId, target)
  if (ok) message.success(target ? '已改判为对' : '已改判为错')
  else message.error('改判失败，该题可能尚未作答')
}

// 结束练习失败时重试保存（finish 失败不置 finished，可重复调用）
async function retryFinish() {
  await store.finish()
  if (store.finishError) message.error(store.finishError)
  else message.success('练习记录已保存')
}

// 标签本地可编辑副本（key=word_id）
const tagState = reactive<Record<number, string[]>>({})
function initTags() {
  for (const q of store.questions) {
    tagState[q.word_id] = (q.tags ?? []).filter((t) => TAGS.some((tt) => tt.value === t))
  }
}
watch(() => store.questions, initTags, { immediate: true })

function hasTag(wordId: number, tag: string) {
  return (tagState[wordId] ?? []).includes(tag)
}

async function toggleTag(wordId: number, tag: string) {
  const prev = tagState[wordId] ?? []
  const cur = new Set(prev)
  if (cur.has(tag)) cur.delete(tag)
  else cur.add(tag)
  const next = [...cur]
  tagState[wordId] = next // 乐观更新
  const r = await api.setTags(wordId, next)
  if (r.code !== 200) {
    message.error(r.message)
    tagState[wordId] = prev // 失败回滚，避免视觉态与后端不一致
  } else {
    const q = store.questions.find((x) => x.word_id === wordId)
    if (q) q.tags = next
  }
}

// 单元进度（跳过虚拟错题本 0）：三态 loading / loaded / failed
interface UStat {
  rate: number
  dist: Record<string, number>
}
type UStatState = UStat | 'loading' | 'failed'
const unitStats = reactive<Record<number, UStatState>>({})

async function loadUnitStats() {
  for (const uid of store.unitIds) {
    if (uid === 0) continue
    unitStats[uid] = 'loading'
    const r = await api.getStatsUnit(uid)
    if (r.code === 200) {
      const d = r.data as { mastery_rate: number; mastery_distribution: Record<string, number> }
      unitStats[uid] = { rate: d.mastery_rate, dist: d.mastery_distribution }
    } else {
      unitStats[uid] = 'failed'
    }
  }
}

onMounted(() => {
  loadUnitStats()
  // 正常完成路径给一次成功反馈（finish 失败时 finishError 非空，不弹，由重试按钮的 toast 负责）
  if (!store.finishError) message.success('练习记录已保存')
})

function unitStatText(uid: number): string {
  const s = unitStats[uid]
  // undefined：loadUnitStats 尚未跑到该 uid（首次渲染）；与 'loading' 同口径。
  if (s === 'loading' || s === undefined) return '加载中…'
  if (s === 'failed') return '加载失败'
  return `${s.rate}%`
}
function unitData(uid: number): UStat | null {
  const s = unitStats[uid]
  return typeof s === 'object' ? s : null
}

function restart() {
  store.restart()
}
</script>

<template>
  <div class="summary">
    <h2 class="done-title">🎉 练习完成！</h2>
    <!-- 结束练习失败：本地统计仍展示，可重试保存到后端 -->
    <NAlert v-if="store.finishError" type="warning" class="finish-error">
      <span>⚠️ 结束练习失败：{{ store.finishError }}（当前为本地统计，可重试保存）</span>
      <div class="retry-actions">
        <NButton size="small" type="primary" @click="retryFinish">🔄 重试保存</NButton>
      </div>
    </NAlert>

    <!-- 统计 -->
    <NCard size="small">
      <NSpace :size="32" wrap>
        <NStatistic label="总题数" :value="stats.total" />
        <NStatistic label="正确数" :value="stats.correct" />
        <NStatistic label="正确率" :value="`${stats.acc}%`" />
      </NSpace>
      <p v-if="store.finishData && store.results.size !== store.finishData.total_count" class="hint">
        * 统计以后端为准（本地记录 {{ store.results.size }} 条）
      </p>
    </NCard>

    <!-- 答题回顾 + 改判 + 标签 -->
    <NCard size="small" title="📝 答题回顾">
      <div class="review">
        <div v-for="q in store.questions" :key="q.word_id" class="rev-row">
          <span class="rev-icon">{{ entryOf(q.word_id)?.isCorrect ? '✅' : '❌' }}</span>
          <div class="rev-body">
            <div class="rev-word">
              <span class="rev-en">{{ q.english }}</span>
              <span class="rev-cn">{{ q.chinese }}</span>
              <span v-if="entryOf(q.word_id)?.userAnswer" class="rev-ua">
                你的作答：{{ entryOf(q.word_id)?.userAnswer }}
              </span>
            </div>
            <div class="rev-actions">
              <NButton
                size="tiny"
                quaternary
                :disabled="!canRejudge(q.word_id)"
                @click="rejudge(q.word_id, !entryOf(q.word_id)?.isCorrect)"
              >
                ↩️ 改判为{{ entryOf(q.word_id)?.isCorrect ? '错' : '对' }}
              </NButton>
              <NTag
                v-for="t in TAGS"
                :key="t.value"
                size="small"
                :type="hasTag(q.word_id, t.value) ? 'success' : 'default'"
                :checkable="false"
                style="cursor: pointer"
                @click="toggleTag(q.word_id, t.value)"
              >
                {{ t.emoji }} {{ t.label }}
              </NTag>
            </div>
          </div>
        </div>
      </div>
    </NCard>

    <!-- 单元进度 -->
    <NCard v-if="store.unitIds.filter((u) => u !== 0).length" size="small" title="📈 本轮涉及 Unit 掌握度">
      <div v-for="uid in store.unitIds.filter((u) => u !== 0)" :key="uid" class="unit-row">
        <div class="unit-head">Unit {{ uid }} · {{ unitStatText(uid) }}</div>
        <NProgress
          v-if="unitData(uid)"
          type="line"
          :percentage="unitData(uid)!.rate"
          :show-indicator="false"
        />
        <div v-if="unitData(uid)" class="dist">
          <span
            v-for="lv in MASTERY_ORDER"
            :key="lv"
            class="dist-chip"
            :style="{ background: masteryMeta(lv).color }"
          >
            {{ masteryMeta(lv).emoji }} {{ unitData(uid)!.dist[lv] ?? 0 }}
          </span>
        </div>
      </div>
    </NCard>

    <NButton type="primary" size="large" @click="restart">🔄 再来一轮</NButton>
  </div>
</template>

<style scoped>
.summary {
  max-width: 860px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.done-title {
  margin: 0;
  text-align: center;
}
.hint {
  color: #999;
  font-size: 12px;
}
.finish-error {
  margin-bottom: 4px;
}
.finish-error .retry-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.review {
  display: flex;
  flex-direction: column;
}
.rev-row {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f2f2f2;
}
.rev-icon {
  font-size: 18px;
}
.rev-body {
  flex: 1;
}
.rev-word {
  font-size: 14px;
  margin-bottom: 6px;
}
.rev-en {
  font-weight: 600;
  margin-right: 10px;
}
.rev-cn {
  color: #666;
}
.rev-ua {
  color: #d03050;
  margin-left: 10px;
  font-size: 13px;
}
.rev-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.unit-row {
  margin-bottom: 14px;
}
.unit-head {
  font-size: 13px;
  color: #555;
  margin-bottom: 4px;
}
.dist {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.dist-chip {
  color: #fff;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 10px;
}
</style>
