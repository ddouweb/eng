<script setup lang="ts">
// 刮刮乐票面组件：真票照片做底盘，25 格按百分比叠加（坐标见 constants/lottery.ts）。
// 从原版 game.js renderTicket/renderTicket 演出部分移植为受控组件：
//   - props.ticket  全量票面（后端下发，含 win_numbers/cells/wins）
//   - props.outcome 非 null = 已开奖 → 中奖格高亮 + 结果覆盖层 + 音效/撒花
//   - emit allRevealed 全部 25 格刮开后发一次（父组件决定自动结算还是进入核对态）
// 票面格子是百分比定位，必须等底图加载完成、布局稳定后再建刮层（onImgLoaded）。
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ticketFront from '@/assets/lottery/ticket-front.jpg'
import {
  AUTO_REVEAL_RATIO,
  BOARD,
  BRUSH_SIZE,
  SPECIAL_SVGS,
  fmtPrize,
} from '@/constants/lottery'
import { createScratchCell, type ScratchCellHandle } from '@/composables/useScratch'
import { useLotterySound } from '@/composables/useLotterySound'
import type { TicketFace } from '@/api/types'

const props = defineProps<{
  ticket: TicketFace
  /** 开奖结果（null=未开奖）；传入即触发高亮 + 覆盖层演出 */
  outcome: { prize: number } | null
  /** 已结算的续刮票：不再刮、不触发 allRevealed（涂层直接全开展示） */
  preSettled?: boolean
}>()

const emit = defineEmits<{
  allRevealed: []
}>()

const sound = useLotterySound()
const imgRef = ref<HTMLImageElement | null>(null)
const cells: ScratchCellHandle[] = []
let coatEls: HTMLCanvasElement[] = []
let cellRects: { x: number; y: number; w: number; h: number }[] = []
let revealedCount = 0
let settledFlag = false
const rollEl = ref<HTMLElement | null>(null)
const overlayShown = ref(false)

const pad = (n: number): string => String(n).padStart(2, '0')

const winStyle = (i: number) => {
  const c = BOARD.winCols[i]
  return { left: `${c.x}%`, top: `${BOARD.winRow.y}%`, width: `${c.w}%`, height: `${BOARD.winRow.h}%` }
}
const myStyle = (i: number) => {
  const col = BOARD.myCols[i % BOARD.myCols.length]
  const y = BOARD.myRows[Math.floor(i / BOARD.myCols.length)]
  return { left: `${col.x}%`, top: `${y}%`, width: `${col.w}%`, height: `${BOARD.cellH}%` }
}

const isWinCell = (i: number): boolean => props.ticket.wins.some((w) => w.idx === i)
const winReasons = (): string => props.ticket.wins.map((w) => w.reason).join(' + ')

function coatRef(el: unknown): void {
  if (el instanceof HTMLCanvasElement) coatEls.push(el)
}

/** 底图加载完成、布局稳定后建刮层；刮层图源 = 同一张票面照片（Vite import 同源，canvas 不被污染） */
async function onImgLoaded(): Promise<void> {
  if (cells.length) return // @load 与 mounted 兜底可能都触发，只建一次
  await nextTick()
  if (!coatEls.length || cells.length) return
  // 每格在整张票面图上的百分比矩形，顺序同 DOM 里的 canvas（5 福袋 + 20 格）
  cellRects = [
    ...BOARD.winCols.map((c) => ({ x: c.x, y: BOARD.winRow.y, w: c.w, h: BOARD.winRow.h })),
    ...Array.from({ length: props.ticket.cells.length }, (_, i) => {
      const col = BOARD.myCols[i % BOARD.myCols.length]
      const y = BOARD.myRows[Math.floor(i / BOARD.myCols.length)]
      return { x: col.x, y, w: col.w, h: BOARD.cellH }
    }),
  ]
  const photoImg = new Image()
  photoImg.src = ticketFront
  const go = (): void => buildCells(photoImg)
  if (photoImg.complete && photoImg.naturalWidth) go()
  else {
    photoImg.addEventListener('load', go, { once: true })
    photoImg.addEventListener('error', () => buildCells(null), { once: true }) // 图源挂了退回手绘涂层
  }
}

function buildCells(photoImg: HTMLImageElement | null): void {
  coatEls.forEach((cv, i) => {
    cells.push(
      createScratchCell(cv, {
        threshold: AUTO_REVEAL_RATIO,
        brush: BRUSH_SIZE,
        photo: photoImg ? { img: photoImg, rect: cellRects[i] } : null,
        symbol: i < BOARD.winCols.length ? 'bag' : '¥',
        onScratchStart: () => sound.startScratch(),
        onScratchEnd: () => sound.stopScratch(),
        onReveal: () => onRevealed(),
      }),
    )
  })
  // 续刮且已结算的票：涂层全开直接展示，不再触发流程
  if (props.preSettled) cells.forEach((c) => c.reveal())
}

function onRevealed(): void {
  if (props.preSettled || settledFlag) return
  revealedCount++
  if (revealedCount < cells.length) return
  settledFlag = true
  emit('allRevealed')
}

/** 一键刮开（父组件经 ref 调用或本组件按钮） */
function revealAll(): void {
  cells.forEach((c) => c.reveal())
}
defineExpose({ revealAll })

/** 金额滚动上升动画 */
function rollNumber(el: HTMLElement, target: number, dur: number): void {
  const t0 = performance.now()
  const tick = (now: number): void => {
    const k = Math.min(1, (now - t0) / dur)
    const ease = 1 - Math.pow(1 - k, 3)
    el.textContent = fmtPrize(target * ease)
    if (k < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

/** 撒花粒子（DOM 实现，结束后自清理） */
function confetti(n: number): void {
  const emo = ['✨', '🎉', '💰', '🪙', '⭐']
  for (let i = 0; i < n; i++) {
    const s = document.createElement('span')
    s.className = 'lottery-confetti'
    s.textContent = emo[Math.floor(Math.random() * emo.length)]
    s.style.left = `${Math.floor(Math.random() * 100)}vw`
    s.style.fontSize = `${14 + Math.floor(Math.random() * 13)}px`
    s.style.animationDuration = `${1.8 + Math.random()}s`
    s.style.animationDelay = `${Math.random() * 0.4}s`
    document.body.appendChild(s)
    setTimeout(() => s.remove(), 3600)
  }
}

// 开奖演出：禁刮 → 中奖格高亮（win-cell class 由 outcome 驱动）→ 覆盖层 + 音效/撒花
watch(
  () => props.outcome,
  (oc) => {
    if (!oc) return
    cells.forEach((c) => c.disable())
    setTimeout(() => {
      overlayShown.value = true
      if (oc.prize > 0) {
        sound.win(oc.prize >= 1000)
        confetti(oc.prize >= 1000 ? 46 : 26)
        nextTick(() => {
          if (rollEl.value) rollNumber(rollEl.value, oc.prize, 1200)
        })
      } else {
        sound.lose()
      }
    }, 550)
  },
)

// 底图从缓存秒开时 @load 可能已错过：mounted 再兜底检查一次
onMounted(() => {
  const img = imgRef.value
  if (img && img.complete && img.naturalWidth) void onImgLoaded()
})

onBeforeUnmount(() => {
  cells.forEach((c) => c.destroy())
  sound.stopScratch()
})
</script>

<template>
  <div class="ticket photo">
    <img
      ref="imgRef"
      class="ticket-img"
      :src="ticketFront"
      alt="点石成金票面（真票照片）"
      @load="onImgLoaded"
    />
    <div class="cells-layer">
      <div v-for="(n, i) in ticket.win_numbers" :key="`w${i}`" class="cell ws" :style="winStyle(i)">
        <div class="num">{{ pad(n) }}</div>
        <canvas class="coat" :ref="coatRef" />
      </div>
      <div
        v-for="(c, i) in ticket.cells"
        :key="`m${i}`"
        class="cell my"
        :class="[c.kind, { 'win-cell': outcome && isWinCell(i) }]"
        :style="myStyle(i)"
      >
        <div v-if="c.kind === 'num'" class="num">{{ pad(c.num ?? 0) }}</div>
        <div v-else class="sym" v-html="SPECIAL_SVGS[c.kind] ?? ''"></div>
        <div class="amt">¥{{ fmtPrize(c.amt) }}</div>
        <span v-if="c.kind === 'rmb'" class="mult-badge">×5</span>
        <canvas class="coat" :ref="coatRef" />
      </div>
      <!-- 结果覆盖层（盖住玩法区，坐标 BOARD.panel；点击收起供人工核对票面） -->
      <div
        v-if="outcome && overlayShown"
        class="result-overlay"
        :class="outcome.prize > 0 ? 'win' : 'lose'"
        :style="{ left: `${BOARD.panel.x}%`, top: `${BOARD.panel.y}%`, width: `${BOARD.panel.w}%`, height: `${BOARD.panel.h}%` }"
        @click="overlayShown = false"
      >
        <button class="overlay-close" title="收起结果，人工核对票面" @click.stop="overlayShown = false">×</button>
        <template v-if="outcome.prize > 0">
          <div class="r-title">🎉 恭喜中奖</div>
          <div class="r-amount"><span ref="rollEl">0</span><small> 彩金</small></div>
          <div class="r-sub">{{ winReasons() }} · 已存入彩金账户</div>
        </template>
        <template v-else>
          <div class="r-title">🙏 谢谢惠顾</div>
          <div class="r-sub">这张没中——学习才是稳赚的彩票</div>
        </template>
      </div>
    </div>
  </div>
  <div class="ticket-actions" v-if="!outcome && !preSettled">
    <button class="btn-ghost" @click="revealAll">🪄 一键刮开</button>
  </div>
</template>

<style scoped>
/* 票面（真票照片做底盘，格子按百分比叠加）——从原版 css/style.css 移植用到的子集 */
.ticket.photo {
  position: relative;
  width: min(100%, 400px);
  margin: 0 auto;
  aspect-ratio: 1264 / 2592;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 12px 38px rgba(0, 0, 0, 0.55);
  container-type: inline-size; /* 格内字号用 cqw 随票宽缩放 */
  background: #7a1610;
}
.ticket-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  user-select: none;
  -webkit-user-drag: none;
  pointer-events: none;
}
.cells-layer {
  position: absolute;
  inset: 0;
}
.cell {
  position: absolute;
  /* 纸面 = 蓝灰渐变（照片取样）+ SVG 噪点做磨损质感 */
  background:
    url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='140'%20height='140'%3E%3Cfilter%20id='n'%3E%3CfeTurbulence%20type='fractalNoise'%20baseFrequency='0.85'%20numOctaves='2'/%3E%3CfeColorMatrix%20values='0%200%200%200%200.08%200%200%200%200%200.13%200%200%200%200%200.18%200%200%200%200%200.45%200'/%3E%3C/filter%3E%3Crect%20width='140'%20height='140'%20filter='url(%23n)'/%3E%3C/svg%3E"),
    linear-gradient(180deg, #c6d9e2, #9cb8c9);
  border: 2px solid rgba(26, 46, 60, 0.55);
  border-radius: 9%;
  box-shadow:
    inset 0 3px 10px rgba(39, 64, 79, 0.22),
    inset 0 -2px 6px rgba(255, 255, 255, 0.28);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  overflow: hidden;
  color: #1a2e3c;
}
/* 字号双写：px 给不支持容器查询的浏览器兜底，cqw 随票宽缩放（原版同款） */
.cell .num {
  font-size: 20px;
  font-size: 6.4cqw;
  font-weight: 900;
  line-height: 1.05;
  letter-spacing: 0.5px;
  text-shadow: 0 0 1px currentColor;
}
.cell .sym {
  font-size: 19px;
  font-size: 6cqw;
  line-height: 1.05;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cell .sym :deep(svg) {
  width: 1.18em;
  height: 1.18em;
  display: block;
}
.cell .amt {
  font-size: 13px;
  font-size: 4.2cqw;
  font-weight: 900;
  color: #1a2e3c;
  letter-spacing: 0.5px;
  line-height: 1.15;
  text-shadow: 0 0 1px currentColor;
}
/* 中奖号码：福袋正中的圆形刮开窗——揭示后红底 + 深墨小数字 */
.cell.ws {
  border: none;
  box-shadow: none;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 38%, #d84f26, #b93312 78%);
}
.cell.ws .num {
  font-size: 20px;
  font-size: 2.8cqw;
  color: #131a2e;
  text-shadow: none;
  transform: none;
}
.mult-badge {
  position: absolute;
  top: 4%;
  right: 5%;
  font-size: 8px;
  font-size: 2.6cqw;
  font-weight: 900;
  color: #fff;
  background: linear-gradient(135deg, #c23a28, #8e1c1c);
  border-radius: 999px;
  padding: 0.2% 4%;
  line-height: 1.5;
}
/* 中奖格高亮：金框外圈 + 金晕脉动 + 号码/金额变红 */
.cell.win-cell {
  outline: 3px solid #f5c451;
  outline-offset: 1px;
  box-shadow:
    0 0 0 5px rgba(245, 196, 81, 0.4),
    0 0 26px rgba(245, 196, 81, 0.95);
  animation: winPop 0.45s ease, winPulse 1s ease-in-out 0.45s infinite;
}
.cell.win-cell .num,
.cell.win-cell .sym,
.cell.win-cell .amt {
  color: #c23a28;
  text-shadow: 0 0 1px currentColor;
}
@keyframes winPop {
  0% {
    transform: scale(0.9);
  }
  55% {
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}
@keyframes winPulse {
  50% {
    box-shadow:
      0 0 0 4px rgba(245, 196, 81, 0.8),
      0 0 36px rgba(245, 196, 81, 1);
  }
}
/* 涂层画布（盖住整格，刮开后露出下面的纸面内容） */
canvas.coat {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: 7%;
  cursor: grab;
  touch-action: none;
  z-index: 2;
}
canvas.coat:active {
  cursor: grabbing;
}
/* 结算覆盖层（盖住票面玩法区） */
.result-overlay {
  position: absolute;
  z-index: 6;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  animation: overlayIn 0.45s ease both;
  cursor: pointer;
}
.result-overlay.win {
  background: radial-gradient(circle at 50% 40%, rgba(255, 248, 220, 0.97), rgba(255, 236, 179, 0.93) 75%);
  box-shadow:
    0 0 0 3px #f5c451,
    0 0 40px rgba(245, 196, 81, 0.7);
}
.result-overlay.lose {
  background: rgba(250, 248, 243, 0.95);
  box-shadow: 0 0 0 2px #d8d3c8;
}
.result-overlay .r-title {
  font-size: 24px;
  font-weight: 900;
  color: #8e1c1c;
}
.result-overlay .r-amount {
  font-size: 44px;
  font-weight: 900;
  color: #c23a28;
  line-height: 1.1;
}
.result-overlay .r-amount small {
  font-size: 20px;
}
.result-overlay.lose .r-title {
  color: #8d8578;
  font-size: 22px;
}
.result-overlay .r-sub {
  font-size: 12px;
  color: #7a6f5e;
}
.overlay-close {
  position: absolute;
  top: 4px;
  right: 8px;
  border: none;
  background: transparent;
  font-family: inherit;
  font-size: 22px;
  line-height: 1;
  color: #a39a8a;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}
.overlay-close:hover {
  color: #4a3b28;
  background: rgba(0, 0, 0, 0.08);
}
@keyframes overlayIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
.ticket-actions {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}
/* 原版金边幽灵按钮（舞台是深色红金底，金字金边才贴原版） */
.btn-ghost {
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  color: #f5c451;
  padding: 8px 18px;
  border-radius: 999px;
  border: 2px solid rgba(245, 196, 81, 0.7);
  background: transparent;
  transition: background 0.15s;
}
.btn-ghost:hover {
  background: rgba(245, 196, 81, 0.12);
}
/* 撒花（挂 body，全局 keyframes 须非 scoped——放在本组件样式外） */
</style>

<style>
/* 撒花粒子动画（粒子挂在 body 上，样式必须全局） */
.lottery-confetti {
  position: fixed;
  top: -30px;
  z-index: 9999;
  pointer-events: none;
  animation: lotteryConfettiFall 2.4s ease-in forwards;
}
@keyframes lotteryConfettiFall {
  to {
    transform: translateY(110vh) rotate(280deg);
    opacity: 0.4;
  }
}
</style>
