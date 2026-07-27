<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSpace,
  NSpin,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { api } from '@/api/client'
import type { Unit } from '@/api/types'

const message = useMessage()
const units = ref<Unit[]>([])
const loading = ref(true)
const creating = ref(false)
const form = reactive({ title: '', sequence: 1 })

async function load() {
  loading.value = true
  const r = await api.listAllUnits()
  if (r.code === 200) units.value = r.data.items
  else message.error(`加载失败：${r.message}`)
  loading.value = false
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
    await load()
  } else {
    message.error(r.message)
  }
}

async function remove(id: number) {
  const r = await api.deleteUnit(id)
  if (r.code === 200) {
    message.success('已删除')
    await load()
  } else {
    message.error(r.message)
  }
}

const columns: DataTableColumns<Unit> = [
  { title: '标题', key: 'title' },
  { title: '序号', key: 'sequence', width: 90 },
  {
    title: '单词数',
    key: 'word_count',
    width: 90,
    render: (row) => String(row.word_count ?? '-'),
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

onMounted(load)
</script>

<template>
  <NSpin :show="loading">
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

    <NCard v-if="!units.length && !loading" size="small">
      还没有 Unit，点击上方「创建新 Unit」开始。
    </NCard>
    <NDataTable v-else :columns="columns" :data="units" :bordered="false" size="small" />

    <p class="hint">
      💡 单人模式下词库经 ECDICT 脚本 / SQL 种子维护；如需新增 Unit，可在此创建后用脚本灌词。
    </p>
  </NSpin>
</template>

<style scoped>
.hint {
  color: #999;
  margin-top: 16px;
  font-size: 13px;
}
</style>
