<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDatePicker,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSpin,
  NTabs,
  NTabPane,
  NTag,
  useDialog,
  useMessage,
  type DialogOptions,
  type SelectOption,
} from 'naive-ui'

import { api } from '@/api/client'
import type { DailyTask, LearningPlan, Unit } from '@/api/types'
import {
  PLAN_STATUS_META,
  PLAN_TYPE_META,
  REBALANCE_REASON_TEXT,
  TASK_TYPE_META,
} from '@/constants/taskIcons'

const message = useMessage()
const dialog = useDialog()

// ── Unit 选项（创建表单用）
const units = ref<Unit[]>([])
const unitOptions = computed<SelectOption[]>(() =>
  units.value.map((u) => ({ label: `${u.title} (ID:${u.id})`, value: u.id })),
)

// ── 表单选项
const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const learnWeekdayOptions: SelectOption[] = WEEKDAY_LABELS.map((label, idx) => ({
  label,
  value: idx,
}))
const planTypeOptions: SelectOption[] = Object.entries(PLAN_TYPE_META).map(([k, v]) => ({
  label: `${v.icon} ${v.label}`,
  value: k,
}))
// SelectOption.value 只支持 string | number，用 0 代表「无」（提交时转回 null）
const monthlyReviewDayOptions: SelectOption[] = [
  { label: '无', value: 0 },
  { label: '月末（最后一天）', value: 31 },
  ...Array.from({ length: 28 }, (_, i) => ({ label: String(i + 1), value: i + 1 })),
]

// 任务状态文案（constants/taskIcons.ts 未提供，本地维护对齐后端 TaskStatus）
type StatusTagType = 'success' | 'warning' | 'default' | 'info' | 'error' | 'primary'
const TASK_STATUS_META: Record<string, { icon: string; label: string; type: StatusTagType }> = {
  completed: { icon: '✅', label: '已完成', type: 'success' },
  in_progress: { icon: '🔄', label: '进行中', type: 'warning' },
  pending: { icon: '⬜', label: '待开始', type: 'default' },
}
const DEFAULT_STATUS = { icon: '⚪', label: '未知', type: 'default' as const }

function planStatusMeta(s: string) {
  return PLAN_STATUS_META[s] ?? DEFAULT_STATUS
}
function planTypeMeta(t: string) {
  return PLAN_TYPE_META[t] ?? { icon: '📅', label: t }
}
function taskTypeMeta(t: string) {
  return TASK_TYPE_META[t] ?? { icon: '📘', label: t }
}
function taskStatusMeta(s: string) {
  return TASK_STATUS_META[s] ?? DEFAULT_STATUS
}

// ── 创建表单
const form = reactive({
  name: '',
  daily_goal: 15,
  unit_ids: [] as number[],
  deadline: null as string | null,
  learn_weekdays: [0, 1, 2, 3, 4] as number[],
  monthly_review_day: 0, // 0 = 无
  plan_type: 'forward',
  start_date: null as string | null,
})
const creating = ref(false)
const canCreate = computed(
  () => !!form.name.trim() && form.unit_ids.length > 0 && form.learn_weekdays.length > 0,
)

function resetForm() {
  form.name = ''
  form.daily_goal = 15
  form.unit_ids = []
  form.deadline = null
  form.learn_weekdays = [0, 1, 2, 3, 4]
  form.monthly_review_day = 0
  form.plan_type = 'forward'
  form.start_date = null
}

async function create() {
  creating.value = true
  const r = await api.createPlan({
    name: form.name.trim(),
    daily_goal: form.daily_goal,
    unit_ids: form.unit_ids,
    deadline: form.deadline || undefined,
    learn_weekdays: form.learn_weekdays,
    monthly_review_day: form.monthly_review_day === 0 ? null : form.monthly_review_day,
    plan_type: form.plan_type,
    start_date: form.start_date || undefined,
  })
  creating.value = false
  if (r.code === 200) {
    message.success(`计划「${form.name.trim() || '新计划'}」创建成功！`)
    resetForm()
    await load()
  } else {
    message.error(r.message)
  }
}

// ── 计划列表（单次拉全部，前端按 tab 过滤）
const loading = ref(true)
const plans = ref<LearningPlan[]>([])
const activePlans = computed(() => plans.value.filter((p) => p.status === 'active'))
const pausedPlans = computed(() => plans.value.filter((p) => p.status === 'paused'))

const tab = ref<'all' | 'active' | 'paused'>('all')
const currentPlans = computed<LearningPlan[]>(() => {
  if (tab.value === 'active') return activePlans.value
  if (tab.value === 'paused') return pausedPlans.value
  return plans.value
})

// ── 每日任务展开缓存（懒加载：首次展开才 getPlan）
const openTasks = ref<Record<number, boolean>>({})
const tasksCache = ref<Record<number, DailyTask[]>>({})
const tasksLoading = ref<Record<number, boolean>>({})
const rebalancing = ref<Record<number, boolean>>({})

async function loadUnits() {
  const r = await api.listAllUnits()
  if (r.code === 200) units.value = r.data.items
  else message.error(`Unit 加载失败：${r.message}`)
}

async function load() {
  loading.value = true
  const r = await api.listPlans()
  loading.value = false
  if (r.code === 200) plans.value = r.data
  else message.error(`计划列表加载失败：${r.message}`)
}

async function pause(id: number) {
  const r = await api.pausePlan(id)
  if (r.code === 200) {
    message.success('已暂停')
    await load()
  } else {
    message.error(r.message)
  }
}

async function resume(id: number) {
  const r = await api.resumePlan(id)
  if (r.code === 200) {
    message.success('已恢复')
    await load()
  } else {
    message.error(r.message)
  }
}

// 重新平衡：仅 plan_type=forward 且 status=active 时可触发。
async function rebalance(p: LearningPlan) {
  rebalancing.value[p.id] = true
  const r = await api.rebalancePlan(p.id)
  rebalancing.value[p.id] = false
  if (r.code !== 200) {
    message.error(r.message)
    return
  }
  const d = r.data
  if (d.feasible) {
    message.success(
      `已重排：每日 ${d.new_per_day ?? '?'} 个新词，剩余 ${d.remaining_learn_days ?? '?'} 天`,
    )
  } else {
    const reason = d.reason ?? ''
    const text = REBALANCE_REASON_TEXT[reason] ?? '无法重平衡'
    const opts: DialogOptions = {
      title: '无法完成重平衡',
      content: text,
      positiveText: '知道了',
    }
    // conflict 表示刚被并发重平衡过，给一个一键重试。
    if (reason === 'conflict') {
      opts.negativeText = '重试'
      opts.onNegativeClick = () => {
        void rebalance(p)
      }
    }
    dialog.warning(opts)
  }
  await load()
}

async function toggleTasks(p: LearningPlan) {
  const next = !openTasks.value[p.id]
  openTasks.value[p.id] = next
  if (next && !tasksCache.value[p.id]) {
    await loadTasks(p.id)
  }
}

async function loadTasks(planId: number) {
  tasksLoading.value[planId] = true
  const r = await api.getPlan(planId)
  tasksLoading.value[planId] = false
  if (r.code === 200) tasksCache.value[planId] = r.data.tasks ?? []
  else message.error(r.message)
}

async function saveTask(planId: number, t: DailyTask) {
  const r = await api.updateTask(planId, t.id, t.completed_new, t.completed_review)
  if (r.code === 200) {
    message.success('已更新')
    await loadTasks(planId)
  } else {
    message.error(r.message)
  }
}

function createdAtShort(p: LearningPlan): string {
  return p.created_at ? p.created_at.slice(0, 10) : '-'
}

onMounted(() => {
  void Promise.all([loadUnits(), load()])
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin: 0 0 16px">📅 学习计划</h2>

    <!-- ── 创建计划 ── -->
    <NCard title="➕ 创建新计划" size="small" style="margin-bottom: 16px">
      <NEmpty v-if="!units.length" description="还没有 Unit，请先添加单词。" />
      <NForm
        v-else
        :model="form"
        label-placement="left"
        :show-feedback="false"
        label-width="92px"
      >
        <NSpace vertical :size="12">
          <NSpace align="center" wrap>
            <NFormItem label="计划名称">
              <NInput
                v-model:value="form.name"
                placeholder="例：在职考研英语一轮"
                style="width: 280px"
              />
            </NFormItem>
            <NFormItem label="计划类型">
              <NSelect
                v-model:value="form.plan_type"
                :options="planTypeOptions"
                style="width: 200px"
              />
            </NFormItem>
          </NSpace>

          <NSpace align="center" wrap>
            <NFormItem label="选择 Unit">
              <NSelect
                v-model:value="form.unit_ids"
                multiple
                :options="unitOptions"
                placeholder="可多选"
                style="min-width: 340px"
              />
            </NFormItem>
            <NFormItem label="每日目标">
              <NInputNumber
                v-model:value="form.daily_goal"
                :min="1"
                :max="200"
                style="width: 150px"
              />
              <span class="suffix">词/天</span>
            </NFormItem>
          </NSpace>

          <NSpace align="center" wrap>
            <NFormItem label="学习日">
              <NSelect
                v-model:value="form.learn_weekdays"
                multiple
                :options="learnWeekdayOptions"
                placeholder="其余为周复习日"
                style="min-width: 340px"
              />
            </NFormItem>
            <NFormItem label="月复习日">
              <NSelect
                v-model:value="form.monthly_review_day"
                :options="monthlyReviewDayOptions"
                style="width: 180px"
              />
            </NFormItem>
          </NSpace>

          <NSpace align="center" wrap>
            <NFormItem label="起始日">
              <NDatePicker
                v-model:formatted-value="form.start_date"
                value-format="yyyy-MM-dd"
                type="date"
                clearable
                placeholder="默认今天"
                style="width: 180px"
              />
            </NFormItem>
            <NFormItem label="截止日期">
              <NDatePicker
                v-model:formatted-value="form.deadline"
                value-format="yyyy-MM-dd"
                type="date"
                clearable
                placeholder="可选"
                style="width: 180px"
              />
            </NFormItem>
            <NButton type="primary" :loading="creating" :disabled="!canCreate" @click="create">
              创建计划
            </NButton>
          </NSpace>
        </NSpace>
      </NForm>
    </NCard>

    <!-- ── 计划列表 ── -->
    <NTabs v-model:value="tab" type="line" animated>
      <NTabPane name="all" tab="全部" />
      <NTabPane name="active" tab="进行中" />
      <NTabPane name="paused" tab="已暂停" />
    </NTabs>

    <NEmpty
      v-if="!currentPlans.length"
      :description="tab === 'all' ? '暂无计划' : `暂无计划（${tab === 'active' ? '进行中' : '已暂停'}）`"
      style="margin-top: 24px"
    />

    <NSpace v-else vertical :size="12" style="margin-top: 12px">
      <NCard v-for="p in currentPlans" :key="p.id" size="small">
        <!-- 头部：名称 + 标签 + 操作 -->
        <div class="plan-head">
          <div class="plan-title">
            <span class="plan-name">{{ planStatusMeta(p.status).icon }} {{ p.name }}</span>
            <NTag :type="planStatusMeta(p.status).type" size="small" round>
              {{ planStatusMeta(p.status).label }}
            </NTag>
            <NTag size="small" round :bordered="false">
              {{ planTypeMeta(p.plan_type).icon }} {{ planTypeMeta(p.plan_type).label }}
            </NTag>
          </div>
          <NSpace align="center" :size="8">
            <NButton
              v-if="p.status === 'active'"
              size="small"
              @click="pause(p.id)"
            >
              ⏸ 暂停
            </NButton>
            <NButton
              v-else-if="p.status === 'paused'"
              size="small"
              type="primary"
              ghost
              @click="resume(p.id)"
            >
              ▶ 继续
            </NButton>
            <NButton
              v-if="p.plan_type === 'forward' && p.status === 'active'"
              size="small"
              type="warning"
              ghost
              :loading="!!rebalancing[p.id]"
              @click="rebalance(p)"
            >
              ⚖️ 重新平衡
            </NButton>
          </NSpace>
        </div>

        <!-- 元信息 -->
        <div class="plan-meta">
          每日目标: {{ p.daily_goal }} 词
          ｜ 起始: {{ p.start_date || '-' }}
          ｜ 截止: {{ p.deadline || '未设置' }}
          ｜ 创建: {{ createdAtShort(p) }}
          <span v-if="p.last_rebalanced_at">
            ｜ 上次重平衡: {{ p.last_rebalanced_at.slice(0, 10) }}
          </span>
        </div>

        <!-- 展开每日任务 -->
        <div class="tasks-toggle">
          <NButton text size="small" @click="toggleTasks(p)">
            {{ openTasks[p.id] ? '▼ 收起每日任务' : '▶ 查看每日任务' }}
          </NButton>
        </div>

        <NSpin :show="!!tasksLoading[p.id]">
          <div v-if="openTasks[p.id]" class="tasks-list">
            <NEmpty
              v-if="!(tasksCache[p.id] && tasksCache[p.id].length)"
              size="small"
              description="暂无任务数据。"
            />
            <div
              v-for="t in tasksCache[p.id] ?? []"
              :key="t.id"
              class="task-row"
            >
              <div class="task-head">
                <span class="task-date">
                  {{ taskStatusMeta(t.status).icon }}
                  {{ taskTypeMeta(t.task_type).icon }}
                  <b>{{ t.task_date }}</b> · {{ taskTypeMeta(t.task_type).label }}
                </span>
                <NTag :type="taskStatusMeta(t.status).type" size="tiny" round>
                  {{ taskStatusMeta(t.status).label }}
                </NTag>
              </div>
              <div class="task-progress">
                新词 {{ t.completed_new }}/{{ t.new_count }}
                ｜ 复习 {{ t.completed_review }}/{{ t.review_count }}
              </div>
              <NSpace v-if="t.status !== 'completed'" align="center" :size="8" class="task-edit">
                <span class="task-edit-label">更新进度：</span>
                <NInputNumber
                  :value="t.completed_new"
                  :min="0"
                  :max="t.new_count"
                  :disabled="t.task_type !== 'learn'"
                  size="small"
                  style="width: 130px"
                  @update:value="(v) => { t.completed_new = v ?? 0 }"
                />
                <NInputNumber
                  :value="t.completed_review"
                  :min="0"
                  :max="t.review_count"
                  size="small"
                  style="width: 130px"
                  @update:value="(v) => { t.completed_review = v ?? 0 }"
                />
                <NButton size="small" type="primary" @click="saveTask(p.id, t)">
                  保存
                </NButton>
              </NSpace>
            </div>
          </div>
        </NSpin>
      </NCard>
    </NSpace>
  </NSpin>
</template>

<style scoped>
.suffix {
  margin-left: 6px;
  color: #888;
  font-size: 13px;
}

.plan-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.plan-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.plan-name {
  font-size: 16px;
  font-weight: 600;
}

.plan-meta {
  color: #888;
  font-size: 13px;
  margin-top: 8px;
}

.tasks-toggle {
  margin-top: 8px;
}

.tasks-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-row {
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 6px;
}

.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-date {
  font-size: 14px;
}

.task-progress {
  color: #666;
  font-size: 13px;
  margin-top: 4px;
}

.task-edit {
  margin-top: 8px;
}

.task-edit-label {
  color: #666;
  font-size: 13px;
}
</style>
