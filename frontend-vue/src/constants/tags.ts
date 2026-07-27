// 单词标签：与后端 TagType 一致；emoji+label 照搬 Streamlit 端 TAG_EMOJI。
export interface TagMeta {
  value: string
  emoji: string
  label: string
}

export const TAGS: TagMeta[] = [
  { value: 'favorite', emoji: '⭐', label: '收藏' },
  { value: 'high_freq', emoji: '🔥', label: '高频' },
  { value: 'exam_focus', emoji: '📚', label: '考试' },
  { value: 'excluded', emoji: '❌', label: '排除' },
  { value: 'memorized', emoji: '✅', label: '已记' },
]

export function tagMeta(value: string): TagMeta | undefined {
  return TAGS.find((t) => t.value === value)
}
