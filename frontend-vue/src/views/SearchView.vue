<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
  type DataTableSortState,
  type SelectOption,
} from 'naive-ui'

import { api } from '@/api/client'
import type { Unit, Word } from '@/api/types'
import { MASTERY_ORDER, masteryMeta } from '@/constants/mastery'
import { TAGS, tagMeta } from '@/constants/tags'
import { formatPhonetic } from '@/composables/usePhonetic'
import { useTtsAudio } from '@/composables/useTtsAudio'

const message = useMessage()
const { play } = useTtsAudio()

// 真服务端分页（NDataTable remote 模式）+ 服务端排序
const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
})
type SearchSortKey = 'english' | 'mastery'
const sortKey = ref<SearchSortKey>('english')
const sortOrder = ref<'ascend' | 'descend'>('ascend')

// Unit 列表：用于「按 Unit 过滤」下拉 + 表格里 unit_id → title 反查（Word 无 unit_title 字段）。
const units = ref<Unit[]>([])
const unitMap = computed(() => new Map<number, string>(units.value.map((u) => [u.id, u.title])))

// '' 表示「（不限）」—— NSelect 的 SelectOption.value 只能 string | number，故用空串做哨兵。
const form = reactive({
  q: '',
  tag: '' as string,
  level: '' as string,
  unitId: '' as string | number,
})

const submitted = ref(false)
const loading = ref(true)
const items = ref<Word[]>([])

const tagOptions: SelectOption[] = [
  { label: '（不限）', value: '' },
  ...TAGS.map((t) => ({ label: `${t.emoji} ${t.label} ${t.value}`, value: t.value })),
]

const levelOptions: SelectOption[] = [
  { label: '（不限）', value: '' },
  ...MASTERY_ORDER.map((lvl) => {
    const m = masteryMeta(lvl)
    return { label: `${m.emoji} ${m.label} ${lvl}`, value: lvl }
  }),
]

const unitOptions = computed<SelectOption[]>(() => [
  { label: '（不限）', value: '' },
  ...units.value.map((u) => ({ label: `${u.title} (ID:${u.id})`, value: u.id })),
])

async function loadUnits() {
  loading.value = true
  const r = await api.listAllUnits()
  if (r.code === 200) units.value = r.data.items
  else message.error(`Unit 列表加载失败：${r.message}`)
  loading.value = false
}

async function doSearch() {
  loading.value = true
  const r = await api.searchWords({
    page: pagination.page,
    page_size: pagination.pageSize,
    sort_by: sortKey.value,
    order: sortOrder.value === 'ascend' ? 'asc' : 'desc',
    ...(form.q.trim() ? { q: form.q.trim() } : {}),
    ...(form.tag ? { tag: form.tag } : {}),
    ...(form.level ? { level: form.level } : {}),
    ...(form.unitId !== '' ? { unit_id: form.unitId as number } : {}),
  })
  loading.value = false
  if (r.code === 200) {
    items.value = r.data.items
    pagination.itemCount = r.data.total
  } else {
    message.error(r.message)
    items.value = []
    pagination.itemCount = 0
  }
}

function search() {
  submitted.value = true
  pagination.page = 1
  void doSearch()
}

function handlePageChange(p: number) {
  pagination.page = p
  void doSearch()
}

function handlePageSizeChange(ps: number) {
  pagination.pageSize = ps
  pagination.page = 1
  void doSearch()
}

// 表头排序：remote 模式下 sorter:true 仅触发事件，由我们回源；回落到默认英文升序。
function onSorterUpdate(sorter: DataTableSortState | DataTableSortState[] | null) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter
  if (s && s.order && (s.columnKey === 'english' || s.columnKey === 'mastery_level')) {
    sortKey.value = s.columnKey === 'mastery_level' ? 'mastery' : 'english'
    sortOrder.value = s.order
  } else {
    sortKey.value = 'english'
    sortOrder.value = 'ascend'
  }
  pagination.page = 1
  void doSearch()
}

const columns = computed<DataTableColumns<Word>>(() => [
  {
    title: '英文',
    key: 'english',
    width: 300,
    sorter: true,
    sortOrder: sortKey.value === 'english' ? sortOrder.value : false,
    render: (row) =>
      h(NSpace, { align: 'center', size: 6 }, () => [
        h('span', { style: 'font-weight:600' }, row.english),
        formatPhonetic(row.phonetic)
          ? h('span', { style: 'color:#6B7280;font-size:13px' }, formatPhonetic(row.phonetic))
          : null,
        h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            circle: true,
            onClick: () => {
              void play(row.english)
            },
          },
          { default: () => '🔊' },
        ),
      ]),
  },
  { title: '中文', key: 'chinese', width: 300, ellipsis: { tooltip: true } },
  {
    title: 'Unit',
    key: 'unit_id',
    render: (row) => unitMap.value.get(row.unit_id) ?? '-',
  },
  {
    title: '掌握度',
    key: 'mastery_level',
    sorter: true,
    sortOrder: sortKey.value === 'mastery' ? sortOrder.value : false,
    render: (row) => {
      const m = masteryMeta(row.mastery_level)
      return h(
        NTag,
        {
          size: 'small',
          round: true,
          color: { color: m.color, textColor: '#fff', borderColor: 'transparent' },
        },
        { default: () => `${m.emoji} ${m.label}` },
      )
    },
  },
  {
    title: '标签',
    key: 'tags',
    render: (row) => {
      const tags = row.tags ?? []
      if (!tags.length) return h('span', { style: 'color:#6B7280' }, '-')
      return h(
        NSpace,
        { size: 4 },
        () =>
          tags.map((t) => {
            const meta = tagMeta(t)
            return h(
              NTag,
              { size: 'small', bordered: false },
              { default: () => `${meta?.emoji ?? ''} ${meta?.label ?? t}` },
            )
          }),
      )
    },
  },
])

onMounted(loadUnits)
</script>

<template>
  <div>
    <h2 style="margin-top: 0">📖 单词查询</h2>
    <p class="caption">
      🔎 跨所有 Unit 搜已收录单词，按关键词/标签/掌握度/Unit 过滤，定位它属于哪个 Unit。每条都带音标与播放，重复播放不重复请求。
    </p>

    <NCard title="🔍 搜索" size="small" style="margin-bottom: 16px">
      <NForm label-placement="left" :show-feedback="false">
        <NSpace vertical :size="12">
          <NFormItem label="关键词（英文或中文，模糊匹配）">
            <NInput
              v-model:value="form.q"
              placeholder="输入英文或中文"
              clearable
              @keyup.enter="search"
              style="width: 320px"
            />
          </NFormItem>
          <NSpace :size="12" wrap>
            <NFormItem label="标签">
              <NSelect v-model:value="form.tag" :options="tagOptions" style="width: 200px" />
            </NFormItem>
            <NFormItem label="掌握度">
              <NSelect v-model:value="form.level" :options="levelOptions" style="width: 200px" />
            </NFormItem>
            <NFormItem label="所在 Unit">
              <NSelect
                v-model:value="form.unitId"
                :options="unitOptions"
                style="width: 240px"
              />
            </NFormItem>
          </NSpace>
          <NButton type="primary" @click="search">🔍 搜索</NButton>
        </NSpace>
      </NForm>
    </NCard>

    <template v-if="!submitted">
      <NEmpty description="输入关键词或选择筛选条件后点「🔍 搜索」" style="margin: 24px 0" />
    </template>
    <template v-else>
      <p class="page-info">共 {{ pagination.itemCount }} 条</p>
      <NEmpty
        v-if="!items.length && !loading"
        description="没有匹配的单词 · 试试调整关键词或筛选条件"
        style="margin: 24px 0"
      />
      <NDataTable
        v-else
        :columns="columns"
        :data="items"
        remote
        :pagination="pagination"
        :loading="loading"
        :bordered="false"
        size="small"
        :row-key="(row) => row.id"
        @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange"
        @update:sorter="onSorterUpdate"
      />
    </template>
  </div>
</template>

<style scoped>
.caption {
  color: #6B7280;
  font-size: 13px;
  margin: 0 0 16px;
}
.page-info {
  color: #6B7280;
  font-size: 13px;
  margin: 0 0 12px;
}
</style>
