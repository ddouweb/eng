// 掌握度四态：与后端 MasteryLevel 一致；颜色对应 styles/tokens.css 的 CSS 变量（全应用同色）。
export type MasteryLevel = 'unlearned' | 'learning' | 'familiar' | 'permanent'

export interface MasteryMeta {
  label: string
  emoji: string
  color: string
}

export const MASTERY_META: Record<MasteryLevel, MasteryMeta> = {
  unlearned: { label: '未学', emoji: '⚪', color: 'var(--mastery-unlearned)' },
  learning: { label: '学习中', emoji: '🟠', color: 'var(--mastery-learning)' },
  familiar: { label: '熟悉', emoji: '🔵', color: 'var(--mastery-familiar)' },
  permanent: { label: '已掌握', emoji: '🟢', color: 'var(--mastery-permanent)' },
}

export const MASTERY_ORDER: MasteryLevel[] = ['unlearned', 'learning', 'familiar', 'permanent']

export function masteryMeta(level: string | null | undefined): MasteryMeta {
  if (level && level in MASTERY_META) return MASTERY_META[level as MasteryLevel]
  return MASTERY_META.unlearned
}
