// 练习模式（11 种，与后端 PracticeMode 对齐，dialogue 归 AI 助手页不在练习页）。
// 标签照搬 Streamlit 练习页 MODES 字典。
export interface PracticeModeMeta {
  value: string
  icon: string
  label: string
}

export const PRACTICE_MODES: PracticeModeMeta[] = [
  { value: 'flashcard', icon: '🃏', label: '单词卡' },
  { value: 'choice', icon: '🔘', label: '英→中 选择' },
  { value: 'cn2en_choice', icon: '🔘', label: '中→英 选择' },
  { value: 'spelling', icon: '✏️', label: '中→英 拼写' },
  { value: 'en2cn_write', icon: '📝', label: '英→中 默写' },
  { value: 'dictation', icon: '🎧', label: '听写' },
  { value: 'matching', icon: '🔗', label: '连连看' },
  { value: 'timed_challenge', icon: '⏱️', label: '限时挑战' },
  { value: 'scramble', icon: '🔀', label: '打乱重排' },
  { value: 'memory_flash', icon: '🧠', label: '记忆闪卡' },
  { value: 'flip_match', icon: '🔍', label: '翻牌寻配' },
]

export function modeMeta(value: string): PracticeModeMeta | undefined {
  return PRACTICE_MODES.find((m) => m.value === value)
}
