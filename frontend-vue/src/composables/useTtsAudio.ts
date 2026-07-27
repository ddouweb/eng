// 统一 TTS 音频：blob 缓存，重复播放零网络。
// 落实项目记忆「音频播放须 blob 缓存，重复播放不再回源」（修复 Streamlit 端 3 套实现中
// 仅单词查询页兑现的问题）。TTS 端点免登录（router.py 注释），故 fetch 无需 Authorization。
import { api } from '@/api/client'

// 模块级缓存：text → ObjectURL（应用生命周期内复用）。
const blobCache = new Map<string, string>()
const inflight = new Map<string, Promise<string | null>>()

async function fetchBlobUrl(text: string): Promise<string | null> {
  const cached = blobCache.get(text)
  if (cached) return cached
  const existing = inflight.get(text)
  if (existing) return existing
  const p = (async () => {
    try {
      const resp = await fetch(api.getTtsUrl(text, 'en'))
      if (!resp.ok) return null
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      blobCache.set(text, url)
      return url
    } catch {
      return null
    } finally {
      inflight.delete(text)
    }
  })()
  inflight.set(text, p)
  return p
}

export function useTtsAudio() {
  /** 播放英文发音：优先 blob 缓存（零网络），失败兜底直链。 */
  async function play(text: string): Promise<void> {
    if (!text) return
    const url = await fetchBlobUrl(text)
    const audio = url ? new Audio(url) : new Audio(api.getTtsUrl(text, 'en'))
    await audio.play().catch(() => {
      // 自动播放策略可能拒绝；静默（由用户手势触发的播放不受影响）
    })
  }
  return { play }
}
