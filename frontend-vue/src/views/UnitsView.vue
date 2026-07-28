<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NProgress,
  NSpace,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { api } from '@/api/client'
import type { MasteryDist, Unit } from '@/api/types'
import { MASTERY_META, MASTERY_ORDER } from '@/constants/mastery'

const message = useMessage()
const units = ref<Unit[]>([])
const loading = ref(true)
const creating = ref(false)
const form = reactive({ title: '', sequence: 1 })

// 每个 Unit 的掌握度统计（getStatsUnit 返回 unknown，此处固化结构）。
interface UnitStats {
  mastery_rate: number
  mastery_distribution: MasteryDist
}
const unitStats = ref<Record<number, UnitStats>>({})
const statsLoading = ref(false)

// 仅拉取当前页 Unit 的掌握度（≤ pageSize 个并发请求）；翻页/增删后随 load() 刷新。
async function loadUnitStats() {
  const targets = units.value.filter((u) => (u.word_count ?? 0) > 0)
  if (!targets.length) {
    unitStats.value = {}
    return
  }
  statsLoading.value = true
  const entries = await Promise.all(
    targets.map(async (u): Promise<[number, UnitStats | null]> => {
      const r = await api.getStatsUnit(u.id)
      if (r.code !== 200) return [u.id, null]
      return [u.id, r.data as UnitStats]
    }),
  )
  const map: Record<number, UnitStats> = {}
  for (const [id, s] of entries) if (s) map[id] = s
  unitStats.value = map
  statsLoading.value = false
}

// 掌握度单元格：进度条 + 四态彩色 chip（颜色取 var(--mastery-*)，与全站一致）。
// 用内联样式而非 scoped class —— column render 经 h() 生成，scoped 哈希不会作用其上。
function renderMastery(row: Unit) {
  const s = unitStats.value[row.id]
  if ((row.word_count ?? 0) === 0) return h('span', { style: 'color:#9ca3af' }, '—')
  if (!s) return h('span', { style: 'color:#9ca3af' }, statsLoading.value ? '加载中…' : '—')
  return h('div', { style: 'min-width:200px' }, [
    h(
      'div',
      { style: 'display:flex;align-items:center;gap:8px;margin-bottom:5px' },
      [
        h(NProgress, {
          type: 'line',
          percentage: s.mastery_rate,
          height: 8,
          showIndicator: false,
          style: 'flex:1',
        }),
        h('span', { style: 'font-size:12px;color:#18a058;white-space:nowrap' }, `${s.mastery_rate}%`),
      ],
    ),
    h(
      'div',
      { style: 'display:flex;gap:4px;flex-wrap:wrap' },
      MASTERY_ORDER.map((lv) =>
        h(
          'span',
          {
            style: `color:#fff;font-size:11px;line-height:16px;padding:0 6px;border-radius:8px;background:${MASTERY_META[lv].color}`,
          },
          `${MASTERY_META[lv].emoji} ${s.mastery_distribution[lv] ?? 0}`,
        ),
      ),
    ),
  ])
}

// 真服务端分页：NDataTable remote 模式，翻页带 page/page_size 回源（后端 order_by sequence）。
const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

async function load(page = pagination.page, pageSize = pagination.pageSize) {
  loading.value = true
  const r = await api.listUnits(page, pageSize)
  loading.value = false
  if (r.code === 200) {
    units.value = r.data.items
    pagination.itemCount = r.data.total
    void loadUnitStats() // 列表先渲染，掌握度随后异步填充
  } else {
    message.error(`加载失败：${r.message}`)
  }
}

function handlePageChange(p: number) {
  pagination.page = p
  void load(p)
}

function handlePageSizeChange(ps: number) {
  pagination.pageSize = ps
  pagination.page = 1
  void load(1, ps)
}

async function create() {
  if (!form.title.trim()) {
    message.warning('请输入标题')
    return
  }
  creating.value = true
  const r = await api.createUnit(form.title.trim(), form.sequence)
  creating.value = false
  if (r.code === 200) {
    message.success(`Unit 创建成功！ID=${r.data.id}`)
    form.title = ''
    form.sequence = 1
    pagination.page = 1
    await load(1)
  } else {
    message.error(r.message)
  }
}

async function remove(id: number) {
  const r = await api.deleteUnit(id)
  if (r.code === 200) {
    message.success('已删除')
    await load()
    // 当前页被删空且回退一页（避免停在空页）
    if (!units.value.length && pagination.page > 1) {
      pagination.page -= 1
      await load()
    }
  } else {
    message.error(r.message)
  }
}

const columns: DataTableColumns<Unit> = [
  { title: '序号', key: 'sequence', width: 72 },
  { title: '标题', key: 'title' },
  {
    title: '单词数',
    key: 'word_count',
    width: 80,
    render: (row) => String(row.word_count ?? '-'),
  },
  {
    title: '掌握度',
    key: 'mastery',
    render: renderMastery,
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row) =>
      h(
        NPopconfirm,
        { onPositiveClick: () => remove(row.id) },
        {
          trigger: () =>
            h(NButton, { size: 'small', type: 'error', ghost: true }, { default: () => '🗑️ 删除' }),
          default: () =>
            `将永久删除「${row.title}」及其全部单词（含掌握度/错题记录），不可恢复。确认？`,
        },
      ),
  },
]

onMounted(() => load(1))
</script>

<template>
  <div>
    <h2 style="margin-top: 0">📚 单元管理</h2>

    <NCard title="➕ 创建新 Unit" size="small" style="margin-bottom: 16px">
      <NSpace align="center">
        <NFormItem label="标题" label-placement="left" :show-feedback="false">
          <NInput v-model:value="form.title" placeholder="Unit 1 - Hello!" style="width: 280px" />
        </NFormItem>
        <NFormItem label="序号" label-placement="left" :show-feedback="false">
          <NInputNumber v-model:value="form.sequence" :min="1" :step="1" style="width: 110px" />
        </NFormItem>
        <NButton type="primary" :loading="creating" @click="create">创建</NButton>
      </NSpace>
    </NCard>

    <!-- 掌握度配色图例（与表格 chip 同色，说明每种颜色代表的状态） -->
    <div v-if="units.length" class="legend">
      <span v-for="lv in MASTERY_ORDER" :key="lv" class="legend-item">
        <span class="legend-dot" :style="{ background: MASTERY_META[lv].color }"></span>
        {{ MASTERY_META[lv].label }}
      </span>
    </div>

    <NEmpty
      v-if="!units.length && !loading"
      description="还没有 Unit · 点击上方「创建新 Unit」开始"
      style="margin: 24px 0"
    />
    <NDataTable
      v-else
      :columns="columns"
      :data="units"
      remote
      :pagination="pagination"
      :loading="loading"
      :bordered="false"
      size="small"
      :row-key="(row) => row.id"
      @update:page="handlePageChange"
      @update:page-size="handlePageSizeChange"
    />

    <p class="hint">
      💡 单人模式下词库经 ECDICT 脚本 / SQL 种子维护；如需新增 Unit，可在此创建后用脚本灌词。
    </p>
  </div>
</template>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 12px;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.hint {
  color: #6B7280;
  margin-top: 16px;
  font-size: 13px;
}
</style>
