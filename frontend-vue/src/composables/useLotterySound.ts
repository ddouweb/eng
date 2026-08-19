// 刮刮乐 WebAudio 合成音效：刮擦白噪声 / 中奖琶音 / 未中奖低音，无需音频文件。
// 从原版 E:\share\caipiao\js\audio.js 移植为模块单例（AudioContext 全局一份）。
// AudioContext 须在用户手势里创建/resume（浏览器自动播放策略）。

let ctx: AudioContext | null = null
let enabled = true
let noiseBuf: AudioBuffer | null = null
let scratchSrc: AudioBufferSourceNode | null = null
let scratchGain: GainNode | null = null

function loadPref(): void {
  try {
    enabled = JSON.parse(localStorage.getItem('eng.lottery.sound') ?? 'true') !== false
  } catch {
    enabled = true
  }
}
loadPref()

/** 在用户手势里调用一次以解锁 AudioContext */
function ensure(): boolean {
  if (!ctx) {
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AC) return false
    ctx = new AC()
  }
  if (ctx.state === 'suspended') void ctx.resume()
  return true
}

function noise(): AudioBuffer {
  if (noiseBuf) return noiseBuf
  const c = ctx!
  const buf = c.createBuffer(1, c.sampleRate, c.sampleRate) // 1 秒白噪声，循环用
  const ch = buf.getChannelData(0)
  for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1
  noiseBuf = buf
  return buf
}

function stopScratch(): void {
  if (!scratchSrc) return
  const c = ctx!
  const src = scratchSrc
  const gain = scratchGain!
  scratchSrc = null
  scratchGain = null
  try {
    gain.gain.cancelScheduledValues(c.currentTime)
    gain.gain.setValueAtTime(gain.gain.value, c.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + 0.08)
    src.stop(c.currentTime + 0.12)
  } catch {
    /* 已停止则忽略 */
  }
}

export function useLotterySound() {
  return {
    get enabled(): boolean {
      return enabled
    },
    /** 音效开关（持久化到 localStorage） */
    toggle(): boolean {
      enabled = !enabled
      try {
        localStorage.setItem('eng.lottery.sound', JSON.stringify(enabled))
      } catch {
        /* 忽略 */
      }
      if (!enabled) stopScratch()
      return enabled
    },
    /** 按住刮卡时的沙沙声（循环噪声 + 带通滤波） */
    startScratch(): void {
      if (!enabled || !ensure() || !ctx || scratchSrc) return
      const c = ctx
      const src = c.createBufferSource()
      src.buffer = noise()
      src.loop = true
      const bp = c.createBiquadFilter()
      bp.type = 'bandpass'
      bp.frequency.value = 2400
      bp.Q.value = 0.8
      const gain = c.createGain()
      gain.gain.setValueAtTime(0.0001, c.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.12, c.currentTime + 0.05)
      src.connect(bp)
      bp.connect(gain)
      gain.connect(c.destination)
      src.start()
      scratchSrc = src
      scratchGain = gain
    },
    stopScratch,
    /** 中奖：上行琶音，奖金越大音符越多 */
    win(big: boolean): void {
      if (!enabled || !ensure() || !ctx) return
      const c = ctx
      const notes = big ? [523.25, 659.25, 783.99, 1046.5, 1318.5] : [523.25, 659.25, 783.99]
      notes.forEach((f, i) => {
        const t0 = c.currentTime + i * 0.11
        const osc = c.createOscillator()
        osc.type = 'triangle'
        osc.frequency.value = f
        const g = c.createGain()
        g.gain.setValueAtTime(0.0001, t0)
        g.gain.exponentialRampToValueAtTime(0.22, t0 + 0.02)
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.5)
        osc.connect(g)
        g.connect(c.destination)
        osc.start(t0)
        osc.stop(t0 + 0.55)
      })
    },
    /** 未中奖：短促低音下落 */
    lose(): void {
      if (!enabled || !ensure() || !ctx) return
      const c = ctx
      const t0 = c.currentTime
      const osc = c.createOscillator()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(240, t0)
      osc.frequency.exponentialRampToValueAtTime(130, t0 + 0.28)
      const g = c.createGain()
      g.gain.setValueAtTime(0.0001, t0)
      g.gain.exponentialRampToValueAtTime(0.15, t0 + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.32)
      osc.connect(g)
      g.connect(c.destination)
      osc.start(t0)
      osc.stop(t0 + 0.35)
    },
  }
}
