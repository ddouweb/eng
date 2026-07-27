<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  useMessage,
  type DataTableColumns,
  type SelectOption,
} from 'naive-ui'

import { api } from '@/api/client'
import type { Unit, Word } from '@/api/types'
import { masteryMeta } from '@/constants/mastery'
import { tagMeta } from '@/constants/tags'
import { formatPhonetic } from '@/composables/usePhonetic'
import { useTtsAudio } from '@/composables/useTtsAudio'

const message = useMessage()
const { play: playRow } = useTtsAudio()

// ── 数据状态
const loading = ref(true)
const units = ref<Unit[]>([])
const currentUnitId = ref<number | null>(null)
const words = ref<Word[]>([])
const total = ref(0)

const unitOptions = computed<SelectOption[]>(() =>
  units.value.map((u) => ({ label: `${u.title} (ID:${u.id})`, value: u.id })),
)

// ── 播放器 blob 缓存（项目硬性不变量：重复播放零网络）
// useTtsAudio 的 blob 缓存为模块私有、不可外部访问，且其 play 不支持语速，
// 故本视图为播放器自建一份独立缓存（仅顶栏播放器用；行内 🔊 走 useTtsAudio 缓存）。
const playerBlobCache = new Map<string, string>()
const playerInflight = new Map<string, Promise<string | null>>()

async function fetchPlayerBlobUrl(text: string): Promise<string | null> {
  const cached = playerBlobCache.get(text)
  if (cached) return cached
  const existing = playerInflight.get(text)
  if (existing) return existing
  const p = (async () => {
    try {
      const resp = await fetch(api.getTtsUrl(text, 'en'))
      if (!resp.ok) return null
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      playerBlobCache.set(text, url)
      return url
    } catch {
      return null
    } finally {
      playerInflight.delete(text)
    }
  })()
  playerInflight.set(text, p)
  return p
}

// ── 播放器状态
const LS_KEY_PREFIX = 'wm_ap_i_' // 与源页一致：按 Unit 记忆播放位置
const SPEED_OPTIONS: SelectOption[] = [
  { label: '0.8×', value: 0.8 },
  { label: '1×', value: 1 },
  { label: '1.2×', value: 1.2 },
  { label: '1.5×', value: 1.5 },
]

const playerIndex = ref(0)
const playerPlaying = ref(false)
const playerSpeed = ref(1)
const playerStatus = ref('点 ▶ 开始连续播放发音（⏮⏭ 切换）')

// 单例 Audio 元素（per 组件实例）；advanceTimer 用于 ended/error 推进下一词。
let playerAudio: HTMLAudioElement | null = null
let advanceTimer: number | null = null

function clearAdvance(): void {
  if (advanceTimer !== null) {
    window.clearTimeout(advanceTimer)
    advanceTimer = null
  }
}

function ensureAudio(): HTMLAudioElement {
  if (playerAudio) return playerAudio
  const a = new Audio()
  a.addEventListener('ended', () => {
    if (!playerPlaying.value) return
    if (playerIndex.value < words.value.length - 1) {
      // 每词播完 setTimeout 播下一（短间隔，自然过渡）
      advanceTimer = window.setTimeout(() => {
        void go(playerIndex.value + 1, true)
      }, 300)
    } else {
      playerPlaying.value = false
      playerStatus.value = '播放完毕'
    }
  })
  a.addEventListener('error', () => {
    // 后端 503/空体/解码失败时 ended 不触发，靠 error 推进，避免连播卡死（与源页一致）
    if (!playerPlaying.value) return
    if (playerIndex.value < words.value.length - 1) {
      playerStatus.value = `（第 ${playerIndex.value + 1} 个音频加载失败，跳过…）`
      advanceTimer = window.setTimeout(() => {
        void go(playerIndex.value + 1, true)
      }, 500)
    } else {
      playerPlaying.value = false
      playerStatus.value = '播放完毕（含加载失败的词）'
    }
  })
  playerAudio = a
  return a
}

function updateStatus(): void {
  if (!words.value.length) {
    playerStatus.value = '（无单词）'
    return
  }
  const w = words.value[playerIndex.value]
  if (!w) return
  const ph = formatPhonetic(w.phonetic)
  playerStatus.value = `第 ${playerIndex.value + 1}/${words.value.length} 个 · ${w.english}${ph ? ' ' + ph : ''} — ${w.chinese}`
}

function savePos(unitId: number, idx: number): void {
  try {
    localStorage.setItem(LS_KEY_PREFIX + String(unitId), String(idx))
  } catch {
    /* localStorage 不可用时静默 */
  }
}

function loadSavedIndex(unitId: number): number {
  try {
    const s = parseInt(localStorage.getItem(LS_KEY_PREFIX + String(unitId)) ?? '', 10)
    if (!isNaN(s) && s >= 0) return s
  } catch {
    /* ignore */
  }
  return 0
}

/** 跳到第 i 个词并加载音频（命中缓存零网络）；autoplay=true 时立即播放。 */
async function go(i: number, autoplay: boolean): Promise<void> {
  if (!words.value.length) return
  const idx = Math.max(0, Math.min(words.value.length - 1, i))
  clearAdvance()
  playerIndex.value = idx
  if (currentUnitId.value != null) savePos(currentUnitId.value, idx)
  updateStatus()
  const w = words.value[idx]
  if (!w) return
  const audio = ensureAudio()
  const url = await fetchPlayerBlobUrl(w.english)
  audio.src = url ?? api.getTtsUrl(w.english, 'en') // blob 失败兜底直链
  audio.playbackRate = playerSpeed.value
  if (autoplay) {
    playerPlaying.value = true
    await audio.play().catch(() => {
      // 自动播放策略可能拒绝；静默（用户手势触发的播放不受影响）
    })
  }
}

function togglePlay(): void {
  if (playerPlaying.value) {
    pause()
  } else {
    void go(playerIndex.value, true)
  }
}

function pause(): void {
  clearAdvance()
  if (playerAudio) playerAudio.pause()
  playerPlaying.value = false
}

function onPrev(): void {
  void go(playerIndex.value - 1, playerPlaying.value)
}

function onNext(): void {
  void go(playerIndex.value + 1, playerPlaying.value)
}

function onSpeedChange(val: string | number | null): void {
  if (typeof val === 'number') playerSpeed.value = val
  if (playerAudio) playerAudio.playbackRate = playerSpeed.value
}

function resetPlayerForUnit(unitId: number): void {
  pause()
  if (playerAudio) playerAudio.src = ''
  playerIndex.value = loadSavedIndex(unitId)
  playerPlaying.value = false
  updateStatus()
}

// ── 数据加载
async function loadUnits(): Promise<void> {
  const r = await api.listAllUnits()
  if (r.code === 200) {
    units.value = r.data.items
  } else {
    message.error(`Unit 列表加载失败：${r.message}`)
    units.value = []
  }
}

async function loadWords(unitId: number): Promise<void> {
  loading.value = true
  // 单次大页（与源页一致）：单人大词库可能几千词，一次性灌入虚拟滚动表
  const r = await api.listWords(unitId, 1, 5000)
  loading.value = false
  if (r.code !== 200) {
    message.error(r.message)
    words.value = []
    total.value = 0
    return
  }
  // 按 seq 排序：seq 缺失者居后，否则按整数升序（镜像源页 _seq_key）
  const sorted = [...r.data.items].sort((a, b) => {
    const ha = a.seq === null || a.seq === undefined
    const hb = b.seq === null || b.seq === undefined
    if (ha !== hb) return ha ? 1 : -1
    return (a.seq as number) - (b.seq as number)
  })
  words.value = sorted
  total.value = r.data.total
  resetPlayerForUnit(unitId)
}

function onSelectUnit(val: string | number | null): void {
  if (typeof val !== 'number') return
  if (val === currentUnitId.value) return
  currentUnitId.value = val
  void loadWords(val)
}

async function refresh(): Promise<void> {
  if (currentUnitId.value != null) await loadWords(currentUnitId.value)
}

// ── 表格列（固定宽度 + nowrap/ellipsis，确保虚拟滚动行高稳定）
const columns: DataTableColumns<Word> = [
  {
    title: '序号',
    key: 'seq',
    width: 70,
    render: (row) => (row.seq === null || row.seq === undefined ? '-' : String(row.seq)),
  },
  {
    title: '英文',
    key: 'english',
    width: 300,
    render: (row) =>
      h(
        'div',
        { style: 'display:flex;align-items:center;gap:6px;white-space:nowrap;overflow:hidden' },
        [
          h('span', { style: 'font-weight:600;overflow:hidden;text-overflow:ellipsis' }, row.english),
          formatPhonetic(row.phonetic)
            ? h('span', { style: 'color:#888;font-size:13px;flex-shrink:0' }, formatPhonetic(row.phonetic))
            : null,
          h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              circle: true,
              onClick: () => {
                void playRow(row.english)
              },
            },
            { default: () => '🔊' },
          ),
        ],
      ),
  },
  {
    title: '中文',
    key: 'chinese',
    width: 300,
    ellipsis: { tooltip: true },
  },
  {
    title: '掌握度',
    key: 'mastery_level',
    width: 120,
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
    width: 200,
    render: (row) => {
      const tags = row.tags ?? []
      if (!tags.length) return h('span', { style: 'color:#999' }, '-')
      return h(
        NSpace,
        { size: 4, wrap: false },
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
]

onMounted(async () => {
  loading.value = true
  await loadUnits()
  if (units.value.length) {
    currentUnitId.value = units.value[0].id
    await loadWords(currentUnitId.value)
  } else {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  pause()
  if (playerAudio) {
    playerAudio.src = ''
    playerAudio = null
  }
})
</script>

<template>
  <NSpin :show="loading">
    <h2 style="margin-top: 0">🔤 单词管理</h2>

    <NCard v-if="!units.length && !loading" size="small">
      还没有 Unit，请先到「单元管理」页面创建。
    </NCard>

    <template v-else>
      <!-- 顶栏：Unit 选择 + 刷新 -->
      <NSpace align="center" :wrap="false" style="margin-bottom: 12px; gap: 12px">
        <NSelect
          :value="currentUnitId"
          :options="unitOptions"
          style="width: 260px"
          placeholder="选择 Unit"
          @update:value="onSelectUnit"
        />
        <NButton :loading="loading" @click="refresh">🔄 刷新</NButton>
      </NSpace>

      <!-- 播放器：按表格词序顺序播放，autoplay 到下一词 -->
      <NSpace v-if="words.length" align="center" :wrap="false" style="margin-bottom: 12px; gap: 6px">
        <NButton :type="playerPlaying ? 'default' : 'primary'" @click="togglePlay">
          {{ playerPlaying ? '⏸' : '▶' }}
        </NButton>
        <NButton quaternary @click="onPrev">⏮</NButton>
        <NButton quaternary @click="onNext">⏭</NButton>
        <NSelect
          :value="playerSpeed"
          :options="SPEED_OPTIONS"
          style="width: 92px"
          @update:value="onSpeedChange"
        />
        <span class="player-status">{{ playerStatus }}</span>
      </NSpace>

      <p v-if="words.length && words.length < total" class="warn">
        ⚠️ 本单元共 {{ total }} 词，单次最多加载 {{ words.length }} 词（后端上限 5000），未全部显示。
      </p>

      <NCard v-if="!words.length && !loading" size="small">
        这个 Unit 还没有单词。
      </NCard>

      <div v-else-if="words.length" class="table-wrap">
        <NDataTable
          :columns="columns"
          :data="words"
          :virtual-scroll="true"
          :flex-height="true"
          :scroll-x="990"
          :bordered="false"
          size="small"
          :row-key="(row) => row.id"
        />
      </div>

      <p class="hint">
        💡 单人模式下词库经 ECDICT 脚本 / SQL 种子维护；本页为只读浏览，如需新增词请用脚本灌词。
      </p>
    </template>
  </NSpin>
</template>

<style scoped>
.player-status {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #444;
}
.table-wrap {
  height: calc(100vh - 240px);
  min-height: 420px;
}
.warn {
  color: #b07900;
  font-size: 13px;
  margin: 0 0 12px;
}
.hint {
  color: #999;
  margin-top: 16px;
  font-size: 13px;
}
</style>
