// 徽章 + 段位元数据。须与后端 app/gamification.py 的 BADGES / LEVELS 保持一致
// （共 35 枚徽章：streak 13 档 / xp 4 档 / 掌握度 4 / 练习量与质量 4 / 模式 1 /
// 错题本 1 / 周结算 8）。增改时两端同步。
export interface BadgeMeta {
  name: string
  icon: string
  desc: string
}

export const BADGES: Record<string, BadgeMeta> = {
  // ── 连续学习 streak（签到/练习均可推进）──
  streak_3:        { name: '三日起步', icon: '🐣', desc: '连续学习满 3 天' },
  streak_7:        { name: '一周坚持', icon: '🔥', desc: '连续学习满 7 天' },
  streak_10:       { name: '十日养成', icon: '🌿', desc: '连续学习满 10 天' },
  streak_20:       { name: '廿日成树', icon: '🌳', desc: '连续学习满 20 天' },
  streak_30:       { name: '月度达人', icon: '🌙', desc: '连续学习满 30 天' },
  streak_40:       { name: '四十不惑', icon: '🍀', desc: '连续学习满 40 天' },
  streak_50:       { name: '半百达成', icon: '🎗️', desc: '连续学习满 50 天' },
  streak_60:       { name: '花甲初度', icon: '🎴', desc: '连续学习满 60 天' },
  streak_70:       { name: '古稀坚持', icon: '🎇', desc: '连续学习满 70 天' },
  streak_80:       { name: '杖朝不辍', icon: '🎆', desc: '连续学习满 80 天' },
  streak_90:       { name: '鲐背之年', icon: '🎰', desc: '连续学习满 90 天' },
  streak_100:      { name: '百日不辍', icon: '💯', desc: '连续学习满 100 天' },
  streak_365:      { name: '载入史册', icon: '🎉', desc: '连续学习满 365 天' },
  // ── XP ──
  xp_100:          { name: '初学乍练', icon: '🌱', desc: '累计 100 XP' },
  xp_1000:         { name: '勤奋学子', icon: '⭐', desc: '累计 1000 XP' },
  xp_5000:         { name: '词汇大师', icon: '🏆', desc: '累计 5000 XP' },
  xp_10000:        { name: '万众瞩目', icon: '🎖️', desc: '累计 10000 XP' },
  // ── 掌握度 ──
  first_permanent: { name: '牢记在心', icon: '🧠', desc: '首个单词达到永久掌握' },
  permanent_50:    { name: '初窥门径', icon: '🧩', desc: '永久掌握 50 个单词' },
  permanent_200:   { name: '熟能生巧', icon: '🏅', desc: '永久掌握 200 个单词' },
  permanent_500:   { name: '融会贯通', icon: '🎓', desc: '永久掌握 500 个单词' },
  // ── 练习量 / 质量 ──
  practice_500:    { name: '勤学不倦', icon: '📝', desc: '累计答题 500 次' },
  practice_2000:   { name: '笔耕不辍', icon: '✍️', desc: '累计答题 2000 次' },
  practice_5000:   { name: '题海达人', icon: '🚀', desc: '累计答题 5000 次' },
  accuracy_90:     { name: '精准射手', icon: '🎯', desc: '累计正确率 ≥90%（且 ≥200 题）' },
  // ── 模式探索 ──
  modes_explorer:  { name: '十项全能', icon: '🎲', desc: '使用过 10 种练习模式' },
  // ── 错题本 ──
  wrongbook_clear: { name: '扫清障碍', icon: '🧹', desc: '错题本清零（无未掌握错题）' },
  // ── 周结算 ──
  week_full_score: { name: '满分周', icon: '🌟', desc: '单周结算满分 100' },
  week_login_7:    { name: '全勤周', icon: '📅', desc: '单周 7 天全部学习' },
  stars_total_30:  { name: '星光璀璨', icon: '✨', desc: '累计获得 30 颗星' },
  perfect_weeks_4: { name: '稳如磐石', icon: '📊', desc: '累计 4 个满分周' },
  unit_master_1:   { name: '攻克一册', icon: '📖', desc: '背完 1 个 Unit（全部掌握）' },
  unit_master_5:   { name: '攻克五册', icon: '📚', desc: '背完 5 个 Unit' },
  plan_complete_1: { name: '圆满开局', icon: '📋', desc: '完成 1 个学习计划' },
  plan_complete_5: { name: '计划通', icon: '🗓️', desc: '完成 5 个学习计划' },
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
