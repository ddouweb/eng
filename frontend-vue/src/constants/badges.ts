// 徽章 + 段位元数据。须与后端 app/gamification.py 的 BADGES / LEVELS 保持一致
// （含 Phase A 新增 week_full_score / week_login_7）。增改时两端同步。
export interface BadgeMeta {
  name: string
  icon: string
  desc: string
}

export const BADGES: Record<string, BadgeMeta> = {
  streak_7: { name: '一周坚持', icon: '🔥', desc: '连续学习满 7 天' },
  streak_30: { name: '月度达人', icon: '🌙', desc: '连续学习满 30 天' },
  streak_100: { name: '百日不辍', icon: '💯', desc: '连续学习满 100 天' },
  xp_100: { name: '初学乍练', icon: '🌱', desc: '累计 100 XP' },
  xp_1000: { name: '勤奋学子', icon: '⭐', desc: '累计 1000 XP' },
  xp_5000: { name: '词汇大师', icon: '🏆', desc: '累计 5000 XP' },
  first_permanent: { name: '牢记在心', icon: '🧠', desc: '首个单词达到永久掌握' },
  week_full_score: { name: '满分周', icon: '🌟', desc: '单周结算满分 100' },
  week_login_7: { name: '全勤周', icon: '📅', desc: '单周 7 天全部学习' },
}

export interface LevelMeta {
  min: number
  name: string
  icon: string
}

// (累计 XP 下限, 段位名, 图标)，与后端 LEVELS 一致。
export const LEVELS: LevelMeta[] = [
  { min: 0, name: '青铜', icon: '🥉' },
  { min: 100, name: '白银', icon: '🥈' },
  { min: 300, name: '黄金', icon: '🥇' },
  { min: 600, name: '铂金', icon: '💠' },
  { min: 1000, name: '钻石', icon: '💎' },
  { min: 2000, name: '大师', icon: '👑' },
]

export const MAX_FREEZE_BALANCE = 5
