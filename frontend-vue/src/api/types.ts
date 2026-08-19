// 后端统一响应信封 + 各实体类型。字段以后端 schemas/services 实际返回为准，
// 不确定的字段标可选，随各批次页面细化。

export interface ApiResp<T = unknown> {
  code: number
  message: string
  data: T
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ── Auth
export interface LoginData {
  token: string
}

// ── Unit
export interface Unit {
  id: number
  title: string
  sequence: number
  created_at?: string | null
  word_count?: number
}

// ── Word
export interface Word {
  id: number
  unit_id: number
  english: string
  chinese: string
  type?: string
  seq?: number | null
  phonetic?: string | null
  definition?: string | null
  pos?: string | null
  example?: string | null
  tags?: string[]
  mastery_level?: string | null
  wrong_count?: number
  correct_count?: number
  ease_factor?: number
  next_review_date?: string | null
}

// ── Mastery / Stats
export interface MasteryDist {
  unlearned: number
  learning: number
  familiar: number
  permanent: number
}

export interface LevelInfo {
  level_index: number
  level_name: string
  level_icon: string
  level_min_xp: number
  next_level_min_xp: number | null
  next_level_name: string | null
  progress: number
  stars: number
  is_max_level: boolean
}

export interface BadgeEarned {
  key: string
  awarded_at: string | null
}

export interface StatsProfile {
  current_streak: number
  longest_streak: number
  freeze_balance: number
  last_active_date: string | null
  total_xp: number
  level: LevelInfo
  badges: BadgeEarned[]
}

export interface ReviewDue {
  due_today: number
  overdue: number
}

export interface StatsOverview {
  total_words: number
  mastery_distribution: MasteryDist
  mastered_count: number
  mastery_rate: number
  practice_session_count: number
  total_questions: number
  total_correct: number
  accuracy: number
  streak_days: number
}

// ── 每日签到 ──
export interface CheckinEncouragement {
  title: string
  message: string
  /** true=AI 个性化寄语；false=AI 不可用、已用真实学习数据兜底 */
  ai_used?: boolean
}
export interface CheckinResult {
  current_streak: number
  longest_streak: number
  freeze_balance: number
  last_active_date: string | null
  /** 本次签到是否为"今日首次活跃"（false=同日重复签到，streak 不变） */
  first_active_today: boolean
}

export interface DailyTrend {
  date: string
  total: number
  correct: number
}

// ── Practice（batch 9 细化）
export interface PracticeQuestion {
  word_id: number
  english: string
  chinese: string
  type?: string
  phonetic?: string | null
  definition?: string | null
  pos?: string | null
  example?: string | null
  weight?: number
  tags?: string[]
  mastery_level?: string | null
  is_due?: boolean
  is_new?: boolean
  overdue_days?: number
  wrong_count?: number
  question_id?: number
  options?: string[] // 仅 choice 模式，服务端生成
  en_options?: string[] // cn2en_choice，前端生成后挂上
}

export interface PracticeStartData {
  session_id: number
  mode?: string
  total?: number
  questions: PracticeQuestion[]
}

export interface MasterySnapshot {
  level: string
  consecutive_correct: number
  correct_count: number
  wrong_count: number
}

export interface StreakSnapshot {
  current_streak: number
  longest_streak: number
  freeze_balance: number
  last_active_date: string | null
}

export interface SubmitResp {
  is_correct: boolean
  correct_answer: string
  mastery: MasterySnapshot
  streak?: StreakSnapshot
  xp_delta?: number
  total_xp?: number
  new_badges?: string[]
}

export interface FinishResp {
  session_id: number
  mode: string
  total_count: number
  correct_count: number
  accuracy: number
  started_at: string | null
  ended_at: string | null
}

export interface RejudgeResp {
  is_correct: boolean
  changed: boolean
  correct_count: number
  accuracy: number
  xp_delta?: number
  total_xp?: number
  mastery: MasterySnapshot
  new_badges?: string[]
}

// ── AI（backend app/services/exercise_service.py）
export interface DialogueLine {
  role: string // 'teacher' | 'student' | 'narrator'
  english: string
  chinese: string
}

export interface DialogueResult {
  scenario: string
  lines: DialogueLine[]
}

export interface ExerciseItem {
  question: string
  options: string[] | null
  answer: string
  explanation: string | null
}

export interface ExerciseResult {
  mode: string // 'choice' | 'fill'
  items: ExerciseItem[]
}

// ── Plans
export interface DailyTask {
  id: number
  plan_id: number
  task_date: string
  new_count: number
  review_count: number
  completed_new: number
  completed_review: number
  status: string
  task_type: string
}

export interface LearningPlan {
  id: number
  member_id: number
  name: string
  daily_goal: number
  deadline: string | null
  status: string
  created_at?: string | null
  learn_weekdays: number[]
  monthly_review_day: number | null
  start_date: string | null
  plan_type: string
  last_rebalanced_at?: string | null
  unit_ids?: number[]
  tasks?: DailyTask[]
}

export interface RebalanceResult {
  plan_id: number
  feasible: boolean
  reason: string | null
  remaining_unmastered: number | null
  remaining_learn_days: number | null
  effective_learn_days: number | null
  new_per_day: number | null
  daily_goal: number
  cap: number
  deadline: string | null
  last_rebalanced_at: string | null
}

// ── Weekly settlement (Phase A) + 现金激励（Cash Incentive）
export interface PlanHealth {
  remaining_unmastered: number
  remaining_learn_days: number | null
  projected_finish: string | null
  on_track: boolean | null
  suggested_daily_goal: number | null
}

export interface WeeklySettlement {
  week_key: string
  week_start: string
  week_end: string
  login_score: number
  new_score: number
  plan_score: number
  total_score: number
  stars: number
  real_days: number
  new_words_learned: number
  plan_completion: number
  bonus_xp: number
  freeze_granted: number
  // 现金激励（CASH_ENABLED 开启时）；未启用/≤2星 → cash_reward=0、cash_tier_label=null
  cash_reward: number
  cash_tier_label: string | null
  badges_granted: string[]
  plan_health: PlanHealth | null
  settled_at: string | null
}

// 今日完成情况（首页「完成情况+建议」卡片，GET /stats/today）
export interface StatsToday {
  today_new_done: number
  today_new_target: number
  today_review_done: number
  today_review_target: number
  today_correct: number
  today_new_words: number
  wrong_book_total: number
  has_active_plan: boolean
  plan_health: PlanHealth | null
}

// 本周进度预估（首页「本周进度」卡，GET /stats/week-progress）
// 与 WeeklySettlement 互补：结算只处理已结束的上周；本接口是「本周进行中」实时预估，
// bonus/cash 为「若此刻结算」的预估展示值，非实际入账。
export interface WeekProgress {
  week_key: string
  week_start: string
  as_of: string
  active_days: number
  exp_days: number
  login_lost_days: number
  login_remaining_days: number
  new_words: number
  weekly_new_target: number
  completed_slots: number
  planned_slots: number
  plan_completion: number
  login_score: number
  new_score: number
  plan_score: number
  login_full: number
  new_full: number
  plan_full: number
  total_score: number
  stars: number
  bonus_xp: number
  cash_reward: number
  cash_tier_label: string | null
  cash_enabled: boolean
  has_active_plan: boolean
}

// 现金里程碑发放记录（unit_complete / cumulative_words / attendance_streak / badge_reward 四类）
export interface CashMilestone {
  milestone_key: string
  milestone_type: 'unit_complete' | 'cumulative_words' | 'attendance_streak' | 'badge_reward'
  threshold: number
  amount: number
  snapshot: Record<string, unknown> | null
  unit_title?: string | null // 仅 unit_complete：unit.title（threshold 是 unit_id 主键，仅 fallback）
  granted_at: string | null
}

// GET /stats/weekly-settlement 响应 data
export interface WeeklySettlementData {
  history: WeeklySettlement[]
  latest: WeeklySettlement | null
  cash_balance: number
  cash_enabled: boolean
  milestones: CashMilestone[]
}

// ── Wrong book
export interface WrongWordItem {
  id: number
  word_id: number
  english: string
  chinese: string
  unit_id: number
  unit_title: string | null
  word_type: string
  added_at: string
  wrong_count: number
  mastery_level: string | null
  mastery_wrong_count: number
  mastery_correct_count: number
}

// ── Lottery（彩票抽卡；票面 JSON 由后端 app/lottery.py build_ticket 下发，前端只渲染）
export interface TicketCell {
  kind: 'num' | 'cash' | 'rmb' | 'gold'
  num?: number // kind=num 时的两位号码
  amt: number // 格下方金额（rmb 格为×5 前的面额）
}

export interface TicketWin {
  idx: number // 命中的「你的号码」格下标（0~19）
  amount: number
  reason: string // 号码匹配 / 现金币 / 人民币×5 / 金砖
}

// 全量票面（后端 lottery_ticket.ticket 列）
export interface TicketFace {
  prize: number
  win_numbers: number[]
  cells: TicketCell[]
  wins: TicketWin[]
}

// GET /lottery/draw 响应 data
export interface LotteryDrawData {
  id: number
  batch_id: string | null
  prize: number
  ticket: TicketFace
  created_at: string
  settled_at: string | null
  draw_count_left: number
}

// 任务清单单项（GET /lottery/state）
export interface LotteryTask {
  key: string
  title: string
  icon: string
  rule: string
  done: boolean
  draws: number
  note: string
}

// 票据摘要（state.recent_tickets / pending_single / history.items）
export interface TicketBrief {
  id: number
  prize: number
  batch_id: string | null
  created_at: string
  settled_at: string | null
}

// 批次摘要内一张票的状态
export interface BatchTicketItem {
  id: number
  index: number
  prize: number
  settled: boolean
  settled_at: string | null
  created_at: string
}

export interface BatchSummary {
  batch_id: string
  size: number
  settled: number
  remaining: number
  total_prize: number
  hit_count: number
  best_prize: number
  tickets: BatchTicketItem[]
}

// GET /lottery/state 响应 data
export interface LotteryStateData {
  draw_count: number
  wealth: number
  total_granted: number
  total_drawn: number
  total_won: number
  hit_count: number
  tasks: LotteryTask[]
  active_batch: BatchSummary | null
  pending_single: TicketBrief | null
  recent_tickets: TicketBrief[]
}

// POST /lottery/draw-batch 响应 data（开批即定局，只回 id 不回 prize）
export interface LotteryBatchData {
  batch_id: string
  count: number
  ticket_ids: number[]
  draw_count_left: number
}

// POST /lottery/tickets/{id}/settle 响应 data
export interface LotterySettleData {
  id: number
  prize: number
  wealth: number
  already_settled: boolean
  batch?: Pick<BatchSummary, 'batch_id' | 'size' | 'settled' | 'remaining' | 'total_prize' | 'hit_count' | 'best_prize'>
}

// GET /lottery/history 响应 data
export interface LotteryHistoryData {
  total: number
  total_won: number
  hit_count: number
  items: TicketBrief[]
}
