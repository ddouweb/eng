// 现金激励展示元数据。须与后端 app/cash.py 的 tier label / milestone_type 保持一致
// （同 badges.ts 与 gamification.py 的同步约定：增改档位/类型时两端同步）。

export interface CashTierMeta {
  label: string
  desc: string
}

// 周现金档位 label → 展示文案（label 来自后端 weekly_settlement.cash_tier_label）。
export const CASH_TIERS: Record<string, CashTierMeta> = {
  '5star_full': { label: '5★ + 满计划', desc: '5 星且计划完成度 ≥100% → ¥50' },
  '5star': { label: '5★', desc: '周报 5 星 → ¥40' },
  '4star_full': { label: '4★ + 满计划', desc: '4 星且计划完成度 ≥100% → ¥30' },
  '4star': { label: '4★', desc: '周报 4 星 → ¥20' },
  '3star': { label: '3★', desc: '周报 3 星 → ¥10' },
}

export interface MilestoneMeta {
  name: string
  icon: string
}

// 里程碑 type → 图标/名称（type 来自后端 cash_milestone.milestone_type）。
export const MILESTONES: Record<string, MilestoneMeta> = {
  unit_complete: { name: '背完 Unit', icon: '📦' },
  cumulative_words: { name: '累计掌握', icon: '📚' },
  attendance_streak: { name: '连续全勤', icon: '🔥' },
}

// 把里程碑记录格式化成展示文案（type + threshold）。
export function milestoneDisplay(m: {
  milestone_type: string
  threshold: number
  unit_title?: string | null
}): { icon: string; title: string } {
  const meta = MILESTONES[m.milestone_type] ?? { name: m.milestone_type, icon: '🏅' }
  switch (m.milestone_type) {
    case 'unit_complete': {
      // unit_title 来自后端 unit.title；threshold 是 unit_id（主键会跳号），仅 fallback。
      const name = (m.unit_title ?? '').trim()
      return { icon: meta.icon, title: name ? `背完 ${name}` : `背完 Unit ${m.threshold}` }
    }
    case 'cumulative_words':
      return { icon: meta.icon, title: `累计掌握 ${m.threshold} 词` }
    case 'attendance_streak':
      return { icon: meta.icon, title: `连续 ${m.threshold} 周全勤` }
    default:
      return { icon: meta.icon, title: meta.name }
  }
}

// 档位 label → 展示名（容错：未知 label 原样返回）。
export function tierLabel(label: string | null): string {
  if (!label) return ''
  return CASH_TIERS[label]?.label ?? label
}
