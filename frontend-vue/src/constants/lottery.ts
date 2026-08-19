// 彩票抽卡展示常量（体彩顶呱刮「点石成金」20 元票）。
// BOARD 坐标从原版 E:\share\caipiao\js\config.js 逐值照抄——所有百分比都在底图
// ticket-front.jpg（1264×2592）上逐格标定，对不齐只改这里，别动组件。
// 后端契约见 app/lottery.py 的 build_ticket：票面 JSON 由后端下发，前端只渲染。

/** 单格百分比矩形（相对整张票面图） */
export interface CellRect {
  x: number
  y: number
  w: number
  h: number
}

export const BOARD = {
  aspect: 2592 / 1264,
  // 中奖号码 5 格 = 5 个红福袋正中的圆形刮开窗（袋中心 x 304/478/652/824/1000px，
  // 红身 y 1368~1436px；圆窗直径 = 袋宽 96px，圆心 y 1402px）
  winCols: [
    { x: 20.3, w: 7.6 },
    { x: 34.0, w: 7.6 },
    { x: 47.8, w: 7.6 },
    { x: 61.4, w: 7.6 },
    { x: 75.3, w: 7.6 },
  ],
  winRow: { y: 52.2, h: 3.7 }, // 圆窗直径 96px（w 7.6%×1264 = h 3.7%×2592）
  // 你的号码 5 列 × 4 行 = 涂层上 20 个 ¥ 印刷符号的加权重心标定：
  // 列中心 x 189/410/630/849/1068px，行中心 y 1582/1761/1944/2124px
  myCols: [
    { x: 6.8, w: 16.2 },
    { x: 24.3, w: 16.2 },
    { x: 41.8, w: 16.2 },
    { x: 59.0, w: 16.2 },
    { x: 76.4, w: 16.2 },
  ],
  myRows: [58.1, 65.1, 72.1, 79.0], // 4 行（行距均等 7.0%）
  cellH: 5.8, // 你的号码格高
  panel: { x: 5, y: 44, w: 90, h: 42 }, // 玩法区（结算覆盖层范围）
  // 注：原版另有 photoCrop {x:0,y:42,w:100,h:46}——配合预裁的 photoData 涂层图源用；
  // Vue 版直接用整张原图按格子百分比取样（useScratch 内已注明与原版公式数学等价），不需要该常量
  coat: ['#e6d75c', '#cbb92d', '#dfd04e'], // 涂层渐变（图源加载失败时的兜底画法）
  coatInk: 'rgba(122, 94, 14, 0.62)', // 兜底涂层上印刷符号（¥）的墨色
  coatLine: 'rgba(96, 72, 16, 0.5)', // 涂层上的印刷格线（圆角描边）
} as const

export const WIN_NUMBER_COUNT = 5
export const MY_CELL_COUNT = 20

// 刮卡手感
export const AUTO_REVEAL_RATIO = 0.55 // 单格刮开面积超过该比例 → 自动整格全开
export const BRUSH_SIZE = 26 // 刮擦笔刷直径（CSS 像素）

// 特殊符号（真票规则：兼中兼得）——内联 SVG，不用 emoji：🪙（Emoji 13）在
// Win10 的 Segoe UI Emoji 里没有，会渲染成豆腐块（原版同款注释）。
// cash 现金币：中该格下方所示金额；rmb 人民币：金额×5；gold 金砖：刮开区金额之和。
export const SPECIAL_SVGS: Record<string, string> = {
  cash: '<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="19.5" fill="#eec643" stroke="#a97b12" stroke-width="3"/><circle cx="24" cy="24" r="14.5" fill="none" stroke="#caa11f" stroke-width="1.6"/><text x="24" y="30.5" font-size="16" font-weight="900" text-anchor="middle" fill="#8a5a0a">¥</text></svg>',
  rmb: '<svg viewBox="0 0 48 48"><rect x="4" y="11" width="40" height="26" rx="4" fill="#2f7d5b" stroke="#1b5e42" stroke-width="2.5"/><rect x="9" y="16" width="30" height="16" rx="2.5" fill="none" stroke="#9fd9bd" stroke-width="1.5"/><text x="24" y="30" font-size="14" font-weight="900" text-anchor="middle" fill="#eafff3">¥</text></svg>',
  gold: '<svg viewBox="0 0 48 48"><path d="M15 15 H33 L38 28 H10 Z" fill="#f5c451" stroke="#a97b12" stroke-width="2"/><path d="M8 30 H40 L35 39 H13 Z" fill="#d9a518" stroke="#a97b12" stroke-width="2"/><path d="M18 18.5 H30 L32 24 H16 Z" fill="#ffe08a"/></svg>',
}

// 奖级表（12 级，与后端 app/lottery.py REAL_ODDS 一致；仅展示用，开奖在后端）。
export interface PrizeTier {
  prize: number
  oneIn: number
}

export const PRIZE_TABLE: PrizeTier[] = [
  { prize: 1000000, oneIn: 1250000 },
  { prize: 100000, oneIn: 200000 },
  { prize: 10000, oneIn: 30000 },
  { prize: 5000, oneIn: 15000 },
  { prize: 1000, oneIn: 3500 },
  { prize: 500, oneIn: 800 },
  { prize: 200, oneIn: 250 },
  { prize: 100, oneIn: 90 },
  { prize: 80, oneIn: 55 },
  { prize: 60, oneIn: 26 },
  { prize: 40, oneIn: 10 },
  { prize: 20, oneIn: 45 },
]

// 理论返还率 / 中奖率（原版 calcOddsStats 同款公式，任务清单/说明文案用）。
export function calcOddsStats(): { rtp: number; hitRate: number } {
  let ret = 0
  let hit = 0
  for (const o of PRIZE_TABLE) {
    const p = 1 / o.oneIn
    ret += o.prize * p
    hit += p
  }
  return { rtp: ret / 20, hitRate: hit }
}

// 金额格式化：千分位（原版 fmt 同款，彩金展示用）。
export function fmtPrize(n: number): string {
  return Math.round(n)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}
