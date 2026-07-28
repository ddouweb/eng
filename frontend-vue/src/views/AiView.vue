<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NEmpty,
  NInput,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSpin,
  NStatistic,
  NTabs,
  NTabPane,
  useMessage,
  type SelectOption,
} from 'naive-ui'

import { api } from '@/api/client'
import type { DialogueResult, ExerciseResult, Unit } from '@/api/types'

const message = useMessage()

// ── Unit 选项（两 tab 共用）
const units = ref<Unit[]>([])
const unitLoading = ref(true)
const unitError = ref(false)
const unitOptions = computed<SelectOption[]>(() =>
  units.value.map((u) => ({ label: `${u.title} (ID:${u.id})`, value: u.id })),
)

async function loadUnits() {
  unitLoading.value = true
  unitError.value = false
  const r = await api.listAllUnits()
  if (r.code === 200) units.value = r.data.items
  else {
    unitError.value = true
    message.error(`加载 Unit 失败：${r.message}`)
  }
  unitLoading.value = false
}

// ── Tab 1: 场景对话
const SCENARIOS = ['日常对话', '购物', '学校', '家庭', '餐厅', '旅行', '看病', '天气']
const scenarioOptions = computed<SelectOption[]>(() =>
  SCENARIOS.map((s) => ({ label: s, value: s })),
)
const ROLE_META: Record<string, { label: string; side: 'left' | 'right' }> = {
  teacher: { label: '👩‍🏫 老师', side: 'left' },
  student: { label: '👦 学生', side: 'right' },
  narrator: { label: '📖 旁白', side: 'left' },
}

const dlgUnitIds = ref<number[]>([])
const dlgScenario = ref('日常对话')
const dlgLoading = ref(false)
const dialogue = ref<DialogueResult | null>(null)

async function genDialogue() {
  if (!dlgUnitIds.value.length) {
    message.warning('请至少选择一个 Unit')
    return
  }
  dlgLoading.value = true
  const r = await api.generateDialogue(dlgUnitIds.value, dlgScenario.value)
  dlgLoading.value = false
  if (r.code === 200) dialogue.value = r.data
  else message.error(r.message)
}

function clearDialogue() {
  dialogue.value = null
}

// ── Tab 2: AI 练习
const MODES: SelectOption[] = [
  { label: '🔘 选择题', value: 'choice' },
  { label: '✏️ 填空题', value: 'fill' },
]

const exUnitIds = ref<number[]>([])
const exMode = ref<string>('choice')
const exLoading = ref(false)
const exercise = ref<ExerciseResult | null>(null)
const answers = reactive<Record<number, string>>({})
const submitted = ref(false)

function resetAnswers() {
  for (const k of Object.keys(answers)) {
    delete answers[Number(k)]
  }
}

async function genExercise() {
  if (!exUnitIds.value.length) {
    message.warning('请至少选择一个 Unit')
    return
  }
  exLoading.value = true
  const r = await api.generateExercise(exUnitIds.value, exMode.value)
  exLoading.value = false
  if (r.code === 200) {
    exercise.value = r.data
    resetAnswers()
    submitted.value = false
  } else {
    message.error(r.message)
  }
}

function submitExercise() {
  submitted.value = true
}

function resetExercise() {
  exercise.value = null
  resetAnswers()
  submitted.value = false
}

const score = computed(() => {
  const items = exercise.value?.items ?? []
  let correct = 0
  items.forEach((item, i) => {
    const u = answers[i]
    if (u && u === item.answer) correct++
  })
  const total = items.length
  return {
    correct,
    total,
    rate: total ? Math.round((correct / total) * 100) : 0,
  }
})

function isCorrect(i: number): boolean {
  const items = exercise.value?.items ?? []
  if (i >= items.length) return false
  const u = answers[i]
  return !!u && u === items[i].answer
}

onMounted(loadUnits)
</script>

<template>
  <NSpin :show="unitLoading">
    <h2 style="margin-top: 0">🤖 AI 助手</h2>

    <NCard v-if="unitError && !unitLoading" size="small">
      <NEmpty description="Unit 加载失败">
        <template #extra>
          <NButton size="small" @click="loadUnits">🔄 重试</NButton>
        </template>
      </NEmpty>
    </NCard>
    <NCard v-else-if="!units.length && !unitLoading" size="small">
      <NEmpty description="还没有 Unit，请先添加单词。" />
    </NCard>

    <NTabs v-else type="line" animated>
      <!-- ── 场景对话 ── -->
      <NTabPane name="dialogue" tab="💬 场景对话">
        <NSpace vertical :size="16">
          <NCard title="💬 场景对话生成" size="small">
            <p class="caption">选择单元和场景，AI 会用这些单词生成一段英语对话。</p>
            <NSpace vertical>
              <NSpace align="center" wrap>
                <span class="field-label">选择 Unit</span>
                <NSelect
                  v-model:value="dlgUnitIds"
                  multiple
                  :options="unitOptions"
                  placeholder="可多选"
                  style="min-width: 320px"
                />
              </NSpace>
              <NSpace align="center" wrap>
                <span class="field-label">对话场景</span>
                <NSelect
                  v-model:value="dlgScenario"
                  :options="scenarioOptions"
                  style="min-width: 200px"
                />
              </NSpace>
              <NSpace>
                <NButton
                  type="primary"
                  :loading="dlgLoading"
                  :disabled="!dlgUnitIds.length"
                  @click="genDialogue"
                >
                  生成对话
                </NButton>
                <NButton v-if="dialogue" @click="clearDialogue">🗑️ 清除对话</NButton>
              </NSpace>
            </NSpace>
          </NCard>

          <NSpin :show="dlgLoading">
            <NCard v-if="dialogue" size="small">
              <div class="dlg-scenario">场景：{{ dialogue.scenario }}</div>
              <div class="dlg-list">
                <div
                  v-for="(line, idx) in dialogue.lines"
                  :key="idx"
                  class="dlg-line"
                  :class="(ROLE_META[line.role]?.side ?? 'left') === 'right' ? 'is-right' : 'is-left'"
                >
                  <div class="avatar">{{ ROLE_META[line.role]?.label ?? '💬' }}</div>
                  <div class="bubble">
                    <div class="en">{{ line.english }}</div>
                    <div class="zh">{{ line.chinese }}</div>
                  </div>
                </div>
              </div>
            </NCard>
          </NSpin>
        </NSpace>
      </NTabPane>

      <!-- ── AI 练习 ── -->
      <NTabPane name="exercise" tab="📝 AI 练习">
        <NSpace vertical :size="16">
          <NCard title="📝 AI 练习题生成" size="small">
            <p class="caption">选择单元和题型，AI 会生成结构化练习题。</p>
            <NSpace vertical>
              <NSpace align="center" wrap>
                <span class="field-label">选择 Unit</span>
                <NSelect
                  v-model:value="exUnitIds"
                  multiple
                  :options="unitOptions"
                  placeholder="可多选"
                  style="min-width: 320px"
                />
              </NSpace>
              <NSpace align="center" wrap>
                <span class="field-label">题型</span>
                <NSelect v-model:value="exMode" :options="MODES" style="min-width: 200px" />
              </NSpace>
              <NButton
                type="primary"
                :loading="exLoading"
                :disabled="!exUnitIds.length"
                @click="genExercise"
              >
                生成练习
              </NButton>
            </NSpace>
          </NCard>

          <NSpin :show="exLoading">
            <NCard v-if="exercise && !submitted" size="small">
              <p class="caption">作答完成后点击「提交答案」批改。</p>
              <div v-for="(item, i) in exercise.items" :key="i" class="ex-item">
                <div class="ex-q">Q{{ i + 1 }}. {{ item.question }}</div>
                <NRadioGroup v-if="item.options" v-model:value="answers[i]">
                  <NSpace vertical>
                    <NRadio v-for="opt in item.options" :key="opt" :value="opt">
                      {{ opt }}
                    </NRadio>
                  </NSpace>
                </NRadioGroup>
                <NInput v-else v-model:value="answers[i]" placeholder="你的答案" />
              </div>
              <NButton type="primary" @click="submitExercise">提交答案</NButton>
            </NCard>

            <NCard v-else-if="exercise && submitted" size="small">
              <div class="score-wrap">
                <NStatistic
                  label="正确率"
                  :value="`${score.correct}/${score.total} (${score.rate}%)`"
                />
              </div>
              <div
                v-for="(item, i) in exercise.items"
                :key="i"
                class="ex-result"
                :class="isCorrect(i) ? 'ok' : 'no'"
              >
                <div class="ex-q">
                  {{ isCorrect(i) ? '✅' : '❌' }} Q{{ i + 1 }}. {{ item.question }}
                </div>
                <div class="ex-line">
                  你的答案：<b>{{ answers[i] || '(未作答)' }}</b>
                  <template v-if="!isCorrect(i)"> ｜ 正确答案：<b>{{ item.answer }}</b></template>
                </div>
                <div v-if="item.explanation" class="ex-expl">💡 {{ item.explanation }}</div>
              </div>
              <NButton style="margin-top: 12px" @click="resetExercise">重新生成</NButton>
            </NCard>
          </NSpin>
        </NSpace>
      </NTabPane>
    </NTabs>
  </NSpin>
</template>

<style scoped>
.caption {
  color: #6B7280;
  font-size: 13px;
  margin: 0 0 12px;
}

.field-label {
  display: inline-block;
  min-width: 70px;
  color: #666;
  font-size: 14px;
}

.dlg-scenario {
  color: #2080f0;
  font-weight: 600;
  margin-bottom: 16px;
}

.dlg-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dlg-line {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.dlg-line.is-right {
  flex-direction: row-reverse;
}

.dlg-line.is-right .bubble {
  background: #e8f5e9;
}

.avatar {
  flex-shrink: 0;
  font-size: 16px;
  white-space: nowrap;
}

.bubble {
  background: #f5f5f5;
  border-radius: 8px;
  padding: 8px 14px;
  max-width: 80%;
}

.bubble .en {
  font-weight: 600;
}

.bubble .zh {
  color: #6B7280;
  font-size: 13px;
  margin-top: 4px;
}

.ex-item {
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.ex-item .ex-q {
  font-weight: 600;
  margin-bottom: 8px;
}

.ex-result {
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.ex-result.ok {
  background: rgba(24, 160, 88, 0.10);
}

.ex-result.no {
  background: rgba(208, 48, 80, 0.10);
}

.ex-result .ex-q {
  font-weight: 600;
  margin-bottom: 4px;
}

.ex-line {
  font-size: 14px;
}

.ex-expl {
  color: #6B7280;
  font-size: 13px;
  margin-top: 6px;
}

.score-wrap {
  margin-bottom: 16px;
}
</style>
