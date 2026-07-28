<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NPopconfirm,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { api } from '@/api/client'
import type { WrongWordItem } from '@/api/types'
import { masteryMeta } from '@/constants/mastery'
import { useTtsAudio } from '@/composables/useTtsAudio'

const message = useMessage()
const { play } = useTtsAudio()

const loading = ref(true)
const items = ref<WrongWordItem[]>([])
const total = ref(0)

// 服务端分页：每次请求一页（page/page_size=50），itemCount 驱动 NDataTable 分页器。
const pagination = reactive({
  page: 1,
  pageSize: 50,
  itemCount: 0,
})

async function load() {
  loading.value = true
  const r = await api.listWrongBook(pagination.page, pagination.pageSize)
  loading.value = false
  if (r.code === 200) {
    items.value = r.data.items
    pagination.itemCount = r.data.total
    // list 接口已返回 total，直接复用，不再单独请求 count 接口
    total.value = r.data.total
  } else {
    message.error(`加载失败：${r.message}`)
  }
}

async function onPlay(text: string) {
  await play(text)
}

async function onRemove(wordId: number, english: string) {
  const r = await api.removeWrongWord(wordId)
  if (r.code === 200) {
    message.success(`已移除 ${english}`)
    // 若当前页删完，回到上一页避免空页
    if (items.value.length === 1 && pagination.page > 1) pagination.page -= 1
    await load()
  } else {
    message.error(r.message)
  }
}

async function onClear() {
  const r = await api.clearWrongBook()
  if (r.code === 200) {
    message.success('已清空错题本')
    pagination.page = 1
    await load()
  } else {
    message.error(r.message)
  }
}

function handlePageChange(p: number) {
  pagination.page = p
  load()
}

function rowKey(row: WrongWordItem) {
  return row.word_id
}

const columns: DataTableColumns<WrongWordItem> = [
  { title: '英文', key: 'english' },
  { title: '中文', key: 'chinese' },
  {
    title: 'Unit',
    key: 'unit_title',
    render: (row) => row.unit_title || '-',
  },
  {
    title: '掌握度',
    key: 'mastery_level',
    render: (row) => {
      const m = masteryMeta(row.mastery_level)
      return h(
        NTag,
        { round: true, bordered: false, color: { color: m.color, textColor: '#fff' } },
        { default: () => `${m.emoji} ${m.label}` },
      )
    },
  },
  {
    title: '错误次数',
    key: 'wrong_count',
    width: 100,
    render: (row) => String(row.wrong_count ?? 0),
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    render: (row) =>
      h(
        NSpace,
        { size: 4, wrap: false },
        {
          default: () => [
            h(
              NButton,
              { size: 'small', quaternary: true, onClick: () => onPlay(row.english) },
              { default: () => '🔊 播放' },
            ),
            h(
              NPopconfirm,
              { onPositiveClick: () => onRemove(row.word_id, row.english) },
              {
                trigger: () =>
                  h(
                    NButton,
                    { size: 'small', type: 'error', ghost: true },
                    { default: () => '移除' },
                  ),
                default: () => `将「${row.english}」移出错题本？`,
              },
            ),
          ],
        },
      ),
  },
]

onMounted(load)
</script>

<template>
  <div>
    <h2 style="margin-top: 0">📕 错题本</h2>
    <p class="caption">练习中答错的题会自动加入。答对不会自动移除，需在此手动管理。</p>

    <NSpace align="center" justify="space-between" style="margin-bottom: 12px">
      <span class="metric">错题总数：<strong>{{ total }}</strong></span>
      <NPopconfirm v-if="total > 0" @positive-click="onClear">
        <template #trigger>
          <NButton type="error" ghost>🗑️ 清空错题本</NButton>
        </template>
        将清空错题本中全部词条，不可恢复。确认？
      </NPopconfirm>
    </NSpace>

    <NCard v-if="!total && !loading" size="small">
      错题本为空。在「练习」中答错的题会自动加入。
    </NCard>
    <NDataTable
      v-else
      :columns="columns"
      :data="items"
      :remote="true"
      :pagination="pagination"
      :loading="loading"
      :row-key="rowKey"
      :bordered="false"
      size="small"
      @update:page="handlePageChange"
    />
  </div>
</template>

<style scoped>
.caption {
  color: #999;
  margin-top: -4px;
  font-size: 13px;
}
.metric {
  font-size: 15px;
}
</style>
