// 刮刮层：每格一块 canvas 银灰涂层，destination-out 擦除；面积超阈值自动整格全开。
// 从原版 E:\share\caipiao\js\scratch.js 的 ScratchCell 类移植为工厂函数：
// 零业务耦合（音效经回调注入），photo 收 { img, rect, crop }——img 用 Vite import
// 的同源 URL 加载（canvas 不被污染，getImageData 才能用于自动开奖判定）。
import { BOARD } from '@/constants/lottery'

export interface ScratchPhoto {
  img: HTMLImageElement
  /** 本格在整张票面图上的百分比矩形 */
  rect: { x: number; y: number; w: number; h: number }
}

export interface ScratchCellOpts {
  threshold?: number
  brush?: number
  photo?: ScratchPhoto | null
  /** 兜底手绘涂层上印的图案：'bag' 红福袋、'¥'，空则印「刮开」 */
  symbol?: string | null
  onReveal?: () => void
  onScratchStart?: () => void
  onScratchEnd?: () => void
}

export interface ScratchCellHandle {
  reveal: () => void
  disable: () => void
  destroy: () => void
}

export function createScratchCell(canvas: HTMLCanvasElement, opts: ScratchCellOpts): ScratchCellHandle {
  const maybeCtx = canvas.getContext('2d', { willReadFrequently: true })
  if (!maybeCtx) {
    // 无 2D 上下文（极老浏览器）：直接视为已揭示，不阻塞流程
    opts.onReveal?.()
    return { reveal: () => {}, disable: () => {}, destroy: () => {} }
  }
  // 判空后的别名：函数声明被提升，TS 不保留 maybeCtx 的收窄，别名让闭包拿到非空类型
  const ctx: CanvasRenderingContext2D = maybeCtx
  const threshold = opts.threshold ?? 0.55
  const brush = opts.brush ?? 26
  const photo = opts.photo ?? null
  const symbol = opts.symbol ?? null
  let revealed = false
  let disabled = false
  let lastPt: { x: number; y: number } | null = null
  let strokes = 0
  let dpr = 1

  // 按设备像素比设定画布尺寸（上限 2，避免高分屏开销过大）
  function resize(): void {
    const rect = canvas.getBoundingClientRect()
    dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.max(1, Math.round(rect.width * dpr))
    canvas.height = Math.max(1, Math.round(rect.height * dpr))
  }

  // 涂层：优先直接画底图照片的对应区域（真实箔面光泽与印刷图案，逐像素一致）；
  // 照片不可用时退回手绘金色渐变 + 符号
  function paint(): void {
    const w = canvas.width
    const h = canvas.height
    const d = dpr

    if (photo && photo.img.naturalWidth) {
      const { img, rect } = photo
      const iw = img.naturalWidth
      const ih = img.naturalHeight
      // rect 是整张票面图的百分比，图源就是整张原图 → 直接按百分比取像素。
      // 原版走 photoData 裁剪图 + photoCrop 线性换算（裁剪图 1px = 原图 1px），
      // (rect.y - crop.y)/crop.h * ih_crop 化简后恰等于 rect.y/100 * ih_orig，两者数学等价
      ctx.drawImage(
        img,
        (rect.x / 100) * iw,
        (rect.y / 100) * ih,
        (rect.w / 100) * iw,
        (rect.h / 100) * ih,
        0,
        0,
        w,
        h,
      )
      // 印刷格线：淡淡的描边，让人看清哪里可以刮——福袋格画圆，¥ 格画圆角矩形
      const lw = Math.max(1.5, 1.6 * d)
      const pad = lw / 2 + Math.max(1, d)
      ctx.beginPath()
      if (symbol === 'bag') {
        ctx.arc(w / 2, h / 2, Math.min(w, h) / 2 - pad, 0, Math.PI * 2)
      } else {
        const r = Math.min(w, h) * 0.1
        ctx.moveTo(pad + r, pad)
        ctx.arcTo(w - pad, pad, w - pad, h - pad, r)
        ctx.arcTo(w - pad, h - pad, pad, h - pad, r)
        ctx.arcTo(pad, h - pad, pad, pad, r)
        ctx.arcTo(pad, pad, w - pad, pad, r)
        ctx.closePath()
      }
      ctx.strokeStyle = BOARD.coatLine
      ctx.lineWidth = lw
      ctx.stroke()
      return
    }

    const c = BOARD.coat
    const g = ctx.createLinearGradient(0, 0, w, h)
    g.addColorStop(0, c[0])
    g.addColorStop(0.5, c[1])
    g.addColorStop(1, c[2])
    ctx.fillStyle = g
    ctx.fillRect(0, 0, w, h)

    const step = Math.max(8, Math.round(Math.min(w, h) * 0.09))
    ctx.strokeStyle = 'rgba(255,255,255,0.14)'
    ctx.lineWidth = Math.max(1.5, 1.5 * d)
    for (let x = -h; x < w; x += step) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x + h, h)
      ctx.stroke()
    }

    if (symbol === 'bag') {
      drawBag(ctx, w, h) // 中奖格：红福袋（内印 ¥），同真票
    } else if (symbol) {
      ctx.fillStyle = BOARD.coatInk
      const fs = Math.round(Math.min(w, h) * 0.52)
      ctx.font = `bold ${fs}px "Microsoft YaHei", sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(symbol, w / 2, h / 2 + fs * 0.05)
    } else {
      ctx.fillStyle = 'rgba(90,75,10,0.55)'
      const fs = Math.max(9, Math.round(Math.min(w, h) * 0.17))
      ctx.font = `bold ${fs}px "Microsoft YaHei", sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('刮 开', w / 2, h / 2)
    }
  }

  // 红福袋图案（canvas 手绘）：红包身 + 金收口 + 顶结 + 金色 ¥
  function drawBag(c: CanvasRenderingContext2D, w: number, h: number): void {
    const bw = w * 0.68
    const bh = h * 0.82
    const x0 = (w - bw) / 2
    const y0 = (h - bh) / 2
    const top = y0 + bh * 0.14
    const bot = y0 + bh
    const r = bw * 0.16
    const lw = Math.max(2, w * 0.03)

    c.beginPath()
    c.moveTo(x0 + r, top)
    c.arcTo(x0 + bw, top, x0 + bw, bot, r)
    c.arcTo(x0 + bw, bot, x0, bot, r)
    c.arcTo(x0, bot, x0, top, r)
    c.arcTo(x0, top, x0 + bw, top, r)
    c.closePath()
    c.fillStyle = '#b3271e'
    c.fill()
    c.lineWidth = lw
    c.strokeStyle = '#7c140e'
    c.stroke()

    c.beginPath()
    c.moveTo(w / 2 - bw * 0.15, top + lw)
    c.lineTo(w / 2, y0 + bh * 0.02)
    c.lineTo(w / 2 + bw * 0.15, top + lw)
    c.closePath()
    c.fillStyle = '#b3271e'
    c.fill()
    c.stroke()

    c.beginPath()
    c.moveTo(x0 + bw * 0.08, top + bh * 0.09)
    c.lineTo(x0 + bw * 0.92, top + bh * 0.09)
    c.strokeStyle = '#ecc75d'
    c.lineWidth = Math.max(2, w * 0.05)
    c.stroke()

    c.fillStyle = '#f6d68a'
    const fs = Math.round(Math.min(bw, bh) * 0.38)
    c.font = `bold ${fs}px "Microsoft YaHei", sans-serif`
    c.textAlign = 'center'
    c.textBaseline = 'middle'
    c.fillText('¥', w / 2, top + bh * 0.55)
  }

  function pt(e: PointerEvent): { x: number; y: number } {
    const r = canvas.getBoundingClientRect()
    return {
      x: (e.clientX - r.left) * dpr,
      y: (e.clientY - r.top) * dpr,
    }
  }

  function drawStroke(a: { x: number; y: number }, b: { x: number; y: number }): void {
    ctx.globalCompositeOperation = 'destination-out'
    ctx.lineWidth = brush * dpr
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.stroke()
    if (++strokes % 5 === 0) checkProgress()
  }

  // 抽样统计透明像素比例（步长 6 设备像素，够快也够准）
  function checkProgress(): void {
    if (revealed || disabled) return
    const w = canvas.width
    const h = canvas.height
    if (!w || !h) return
    const data = ctx.getImageData(0, 0, w, h).data
    let clear = 0
    let total = 0
    for (let y = 0; y < h; y += 6) {
      for (let x = 0; x < w; x += 6) {
        total++
        if (data[(y * w + x) * 4 + 3] < 120) clear++
      }
    }
    if (total && clear / total >= threshold) reveal()
  }

  function onDown(e: PointerEvent): void {
    if (revealed || disabled) return
    e.preventDefault()
    try {
      canvas.setPointerCapture(e.pointerId)
    } catch {
      /* 忽略 */
    }
    lastPt = pt(e)
    drawStroke(lastPt, lastPt)
    opts.onScratchStart?.()
  }

  function onMove(e: PointerEvent): void {
    if (revealed || disabled || !lastPt) return
    const p = pt(e)
    drawStroke(lastPt, p)
    lastPt = p
  }

  function onEnd(): void {
    if (!lastPt) return
    lastPt = null
    opts.onScratchEnd?.()
    checkProgress()
  }

  /** 整格揭示（达到阈值 / 一键刮开 / 结算时调用） */
  function reveal(): void {
    if (revealed) return
    revealed = true
    lastPt = null
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    opts.onScratchEnd?.()
    opts.onReveal?.()
  }

  canvas.addEventListener('pointerdown', onDown)
  canvas.addEventListener('pointermove', onMove)
  canvas.addEventListener('pointerup', onEnd)
  canvas.addEventListener('pointercancel', onEnd)
  canvas.addEventListener('lostpointercapture', onEnd)

  resize()
  paint()

  return {
    reveal,
    disable() {
      disabled = true
    },
    destroy() {
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onEnd)
      canvas.removeEventListener('pointercancel', onEnd)
      canvas.removeEventListener('lostpointercapture', onEnd)
    },
  }
}
