// 练习选项/打乱生成器（照 Streamlit 源页 L82-107）。干扰项来自本次 session 题集，
// 与后端 choice 的 _generate_options 同源口径。
import type { PracticeQuestion } from '@/api/types'

export function shuffle<T>(arr: readonly T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// 复刻后端 practice_service._server_judge._norm：小写 + 仅保留字母数字。
// 用于干扰项去重与「与正确项归一化相同则排除」，使客户端判定与服务端复判口径一致
// （否则如「苹果。」与「苹果」客户端 === 判异、服务端 _norm 判同，造成反馈/统计分歧）。
export function normKey(s: string): string {
  // 与后端 PracticeService._normalize 口径一致：小写 + 仅保留 Unicode 字母数字（含汉字），
  // 去标点/空白。原 /[^a-z0-9]/ 会把纯中文全删成空串，导致 pickDistractors 误把所有
  // 中文干扰项判为「与正确项相同」而排除（限时挑战中文选项退化）。
  return Array.from(s.toLowerCase()).filter((ch) => /[\p{L}\p{N}]/u.test(ch)).join('')
}

function pickDistractors(pool: string[], correct: string, n: number): string[] {
  const correctKey = normKey(correct)
  const seen = new Set<string>()
  const candidates: string[] = []
  for (const s of pool) {
    if (!s) continue
    const key = normKey(s)
    if (key === correctKey) continue // 与正确项归一化相同 → 排除（避免客户端判错而服务端判对的分歧项）
    if (seen.has(key)) continue // 干扰项之间按归一化键去重，避免重复值撞 v-for :key / radio 串扰
    seen.add(key)
    candidates.push(s)
  }
  return shuffle(candidates).slice(0, n)
}

/** 中→英选择：从 session 题集取其它词的 english 做干扰项。 */
export function genEnOptions(q: PracticeQuestion, all: PracticeQuestion[], n = 4): string[] {
  const size = Math.max(2, Math.min(n, all.length))
  const distractors = pickDistractors(
    all.map((x) => x.english),
    q.english,
    size - 1,
  )
  return shuffle([q.english, ...distractors])
}

/** 英→中/限时：从 session 题集取其它词的 chinese 做干扰项。 */
export function genCnOptions(q: PracticeQuestion, all: PracticeQuestion[], n = 4): string[] {
  const size = Math.max(2, Math.min(n, all.length))
  const distractors = pickDistractors(
    all.map((x) => x.chinese),
    q.chinese,
    size - 1,
  )
  return shuffle([q.chinese, ...distractors])
}

/** 打乱重排：打散字母，尽量不等于原词。 */
export function scramble(word: string): string {
  const letters = word.split('')
  if (letters.length <= 1) return word
  for (let attempt = 0; attempt < 10; attempt++) {
    const s = shuffle(letters).join('')
    if (s.toLowerCase() !== word.toLowerCase()) return s
  }
  return shuffle(letters).join('')
}
