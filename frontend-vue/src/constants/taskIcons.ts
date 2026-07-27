// 学习计划相关：任务类型 / 计划状态 / 计划类型 的图标+文案。与后端 enums 对齐。
export const TASK_TYPE_META: Record<string, { icon: string; label: string }> = {
  learn: { icon: '📘', label: '学习' },
  weekly_review: { icon: '🔁', label: '周复习' },
  monthly_review: { icon: '📅', label: '月复习' },
  wrong_word_drill: { icon: '🎯', label: '错题刷' },
}

export const PLAN_STATUS_META: Record<
  string,
  { icon: string; label: string; type: 'success' | 'warning' | 'default' }
> = {
  active: { icon: '▶️', label: '进行中', type: 'success' },
  paused: { icon: '⏸️', label: '已暂停', type: 'warning' },
  completed: { icon: '✅', label: '已完成', type: 'default' },
}

export const PLAN_TYPE_META: Record<string, { icon: string; label: string }> = {
  forward: { icon: '🆕', label: '首轮学新词' },
  review_only: { icon: '🔁', label: '二轮纯复习' },
  wrong_word_drill: { icon: '🎯', label: '三轮错题刷' },
}

// rebalance 返回的 reason → 用户可读文案（Phase C）。
export const REBALANCE_REASON_TEXT: Record<string, string> = {
  not_rebalanceable: '该计划类型/状态不支持重平衡（仅 active 的首轮计划可重排）',
  no_deadline: '计划无 deadline，无法计算剩余学习日',
  nothing_to_rebalance: '已无未掌握词，无需重平衡',
  deadline_passed: 'deadline 已过或其前已无学习日，救不回了',
  no_free_learn_days: '未来学习日都已被手动占用，没有可重排的日子',
  infeasible: '即便按上限 1.5× 也很难在 deadline 前背完，已按上限重排，请考虑延长期限或增加学习日',
  conflict: '该计划刚被并发重平衡过，请重试',
}
