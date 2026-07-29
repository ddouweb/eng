// 统一 API 客户端：axios 实例 + 拦截器（Bearer token / 401 跳登录 / 解 {code,message,data}）。
// 1:1 镜像 Streamlit 端 frontend/api_client/client.py，供 Vue 全应用复用。单人模式 member_id=1。
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

import type {
  ApiResp,
  CheckinEncouragement,
  CheckinResult,
  DailyTrend,
  DialogueResult,
  ExerciseResult,
  FinishResp,
  LearningPlan,
  LoginData,
  Page,
  PracticeStartData,
  RebalanceResult,
  RejudgeResp,
  ReviewDue,
  StatsOverview,
  StatsProfile,
  SubmitResp,
  Unit,
  WeeklySettlementData,
  Word,
  WrongWordItem,
} from './types'

const MEMBER_ID = 1 // 单人模式
const BASE = '/api/v1' // vite dev proxy → 后端 :8000

export const TOKEN_KEY = 'fec_token'

const http = axios.create({ baseURL: BASE, timeout: 30000 })

// 请求拦截：带 Bearer
http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// 业务 401（token 失效）→ 清登录态并通知（router 注册跳转）。登录接口 401=凭证错误，不清。
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  unauthorizedHandler = fn
}

// 解包 + 错误统一在 request 里做（try/catch），类型干净。拦截器只管请求侧加 Bearer。
async function request<T>(method: string, url: string, cfg: AxiosRequestConfig = {}): Promise<ApiResp<T>> {
  try {
    const resp = await http.request({ method, url, ...cfg })
    return resp.data as ApiResp<T>
  } catch (err) {
    const e = err as AxiosError
    const status = e.response?.status
    const reqUrl = e.config?.url ?? ''
    if (status === 401 && !reqUrl.includes('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY)
      unauthorizedHandler?.()
    }
    const body = e.response?.data as ApiResp | undefined
    if (body && typeof body.code === 'number') return body as ApiResp<T>
    if (!e.response) {
      return { code: 503, message: '无法连接到服务器，请检查后端是否启动', data: null } as ApiResp<T>
    }
    return { code: status ?? 500, message: body?.message || e.message || '请求失败', data: null } as ApiResp<T>
  }
}

interface SearchWordsParams {
  q?: string
  tag?: string
  level?: string
  unit_id?: number
  word_type?: string
  page?: number
  page_size?: number
  sort_by?: 'english' | 'mastery'
  order?: 'asc' | 'desc'
}

interface CreatePlanInput {
  name: string
  daily_goal: number
  unit_ids: number[]
  deadline?: string | null
  learn_weekdays?: number[]
  monthly_review_day?: number | null
  start_date?: string | null
  plan_type?: string
}

export const api = {
  // ── Auth
  login(username: string, password: string): Promise<ApiResp<LoginData>> {
    return request<LoginData>('post', '/auth/login', { data: { username, password } }).then((r) => {
      if (r.code === 200 && r.data?.token) localStorage.setItem(TOKEN_KEY, r.data.token)
      return r
    })
  },
  logout() {
    localStorage.removeItem(TOKEN_KEY)
  },
  getToken() {
    return localStorage.getItem(TOKEN_KEY)
  },

  // ── Units
  listUnits: (page = 1, pageSize = 20) =>
    request<Page<Unit>>('get', '/units', { params: { page, page_size: pageSize } }),
  async listAllUnits(pageSize = 100): Promise<ApiResp<Page<Unit>>> {
    const all: Unit[] = []
    let page = 1
    let total = 0
    for (;;) {
      const r = await this.listUnits(page, pageSize)
      if (r.code !== 200) return r
      const items = r.data.items
      total = r.data.total
      all.push(...items)
      if (items.length < pageSize || all.length >= total) break
      page++
    }
    return {
      code: 200,
      message: 'OK',
      data: { items: all, total: total || all.length, page: 1, page_size: all.length },
    }
  },
  getUnit: (id: number) => request<Unit>('get', `/units/${id}`),
  createUnit: (title: string, sequence: number) =>
    request<Unit>('post', '/units', { data: { title, sequence } }),
  deleteUnit: (id: number) => request<null>('delete', `/units/${id}`),

  // ── Words
  listWords: (
    unitId: number,
    page = 1,
    pageSize = 50,
    wordType?: string,
    sortBy: 'seq' | 'english' | 'mastery' = 'seq',
    order: 'asc' | 'desc' = 'asc',
  ) =>
    request<Page<Word>>('get', `/words/units/${unitId}/words`, {
      params: {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        order,
        ...(wordType ? { type: wordType } : {}),
      },
    }),
  searchWords: (p: SearchWordsParams) =>
    request<Page<Word>>('get', '/words/search', {
      params: { member_id: MEMBER_ID, page: p.page ?? 1, page_size: p.page_size ?? 50, sort_by: p.sort_by ?? 'english', order: p.order ?? 'asc', ...(p.q ? { q: p.q } : {}), ...(p.tag ? { tag: p.tag } : {}), ...(p.level ? { level: p.level } : {}), ...(p.unit_id ? { unit_id: p.unit_id } : {}), ...(p.word_type ? { type: p.word_type } : {}) },
    }),
  batchCreateWords: (unitId: number, words: Array<Record<string, unknown>>) =>
    request<unknown>('post', `/words/units/${unitId}/words`, { data: { words } }),
  updateWord: (wordId: number, data: Record<string, unknown>) =>
    request<Word>('put', `/words/${wordId}`, { data }),
  deleteWord: (wordId: number) => request<null>('delete', `/words/${wordId}`),
  setTags: (wordId: number, tags: string[]) =>
    request<null>('post', `/words/${wordId}/tags`, { data: { tags } }),
  removeTag: (wordId: number, tag: string) =>
    request<null>('delete', `/words/${wordId}/tags/${tag}`),

  // ── Practice
  startPractice: (mode: string, unitIds: number[], count = 10, taskType?: string) => {
    const data: Record<string, unknown> = { member_id: MEMBER_ID, mode, unit_ids: unitIds, count }
    if (taskType) data.task_type = taskType
    return request<PracticeStartData>('post', '/practice/start', { data })
  },
  submitAnswer: (sessionId: number, wordId: number, isCorrect: boolean, userAnswer?: string | null) =>
    request<SubmitResp>('post', `/practice/${sessionId}/submit`, {
      data: { word_id: wordId, is_correct: isCorrect, user_answer: userAnswer ?? null },
    }),
  finishPractice: (sessionId: number) =>
    request<FinishResp>('post', `/practice/${sessionId}/finish`),
  rejudgeAnswer: (sessionId: number, wordId: number, isCorrect: boolean) =>
    request<RejudgeResp>('post', `/practice/${sessionId}/rejudge`, {
      data: { word_id: wordId, is_correct: isCorrect },
    }),
  getPracticeSession: (sessionId: number) =>
    request<unknown>('get', `/practice/${sessionId}`),

  // ── Plans
  createPlan: (input: CreatePlanInput) => {
    const data: Record<string, unknown> = {
      name: input.name,
      daily_goal: input.daily_goal,
      unit_ids: input.unit_ids,
      learn_weekdays: input.learn_weekdays ?? [0, 1, 2, 3, 4],
    }
    if (input.deadline) data.deadline = input.deadline
    if (input.monthly_review_day != null) data.monthly_review_day = input.monthly_review_day
    if (input.start_date) data.start_date = input.start_date
    if (input.plan_type) data.plan_type = input.plan_type
    return request<LearningPlan>('post', '/plans', { data })
  },
  listPlans: (status?: string) =>
    request<LearningPlan[]>('get', '/plans', { params: status ? { status } : {} }),
  getPlan: (id: number) => request<LearningPlan>('get', `/plans/${id}`),
  updateTask: (planId: number, taskId: number, completedNew: number, completedReview: number) =>
    request<unknown>('put', `/plans/${planId}/tasks/${taskId}`, {
      data: { completed_new: completedNew, completed_review: completedReview },
    }),
  pausePlan: (id: number) => request<null>('post', `/plans/${id}/pause`),
  resumePlan: (id: number) => request<null>('post', `/plans/${id}/resume`),
  rebalancePlan: (id: number) => request<RebalanceResult>('post', `/plans/${id}/rebalance`),

  // ── Stats
  getStatsOverview: () =>
    request<StatsOverview>('get', '/stats/overview', { params: { member_id: MEMBER_ID } }),
  getStatsUnit: (unitId: number) =>
    request<unknown>('get', `/stats/units/${unitId}`, { params: { member_id: MEMBER_ID } }),
  getStatsTrend: (days = 30) =>
    request<{ days: number; daily: DailyTrend[] }>('get', '/stats/trend', {
      params: { days, member_id: MEMBER_ID },
    }),
  getStatsProfile: () =>
    request<StatsProfile>('get', '/stats/profile', { params: { member_id: MEMBER_ID } }),

  // ── Check-in（每日签到：AI 励学寄语 + 确认签到标记今日活跃）
  checkinEncouragement: () =>
    request<CheckinEncouragement>('post', '/checkin/encouragement', {
      params: { member_id: MEMBER_ID },
    }),
  checkin: () => request<CheckinResult>('post', '/checkin', { params: { member_id: MEMBER_ID } }),
  getWeeklySettlement: () =>
    request<WeeklySettlementData>(
      'get',
      '/stats/weekly-settlement',
      { params: { member_id: MEMBER_ID } },
    ),
  getReviewDue: (unitIds?: number[], limit = 50) => {
    const params: Record<string, unknown> = { member_id: MEMBER_ID, limit }
    if (unitIds?.length) params.unit_ids = unitIds.join(',')
    return request<ReviewDue>('get', '/review/due', { params })
  },

  // ── AI
  generateDialogue: (unitIds: number[], scenario = '日常对话') =>
    request<DialogueResult>('post', '/ai/dialogue', { data: { unit_ids: unitIds, scenario } }),
  generateExercise: (unitIds: number[], mode = 'choice') =>
    request<ExerciseResult>('post', '/ai/exercise', { data: { unit_ids: unitIds, mode } }),
  parseWords: (text: string) => request<unknown>('post', '/ai/parse-words', { data: { text } }),

  // ── TTS（直链；实际播放走 useTtsAudio composable 做 blob 缓存）
  getTtsUrl: (text: string, lang = 'en') =>
    `${BASE}/tts/generate?text=${encodeURIComponent(text)}&lang=${lang}`,

  // ── Wrong book
  listWrongBook: (
    page = 1,
    pageSize = 50,
    sortBy: 'added_at' | 'wrong_count' | 'english' = 'added_at',
    order: 'asc' | 'desc' = 'desc',
  ) =>
    request<Page<WrongWordItem>>('get', '/wrong-book', {
      params: { member_id: MEMBER_ID, page, page_size: pageSize, sort_by: sortBy, order },
    }),
  countWrongBook: () =>
    request<{ total: number }>('get', '/wrong-book/count', { params: { member_id: MEMBER_ID } }),
  removeWrongWord: (wordId: number) =>
    request<null>('delete', `/wrong-book/${wordId}`, { params: { member_id: MEMBER_ID } }),
  clearWrongBook: () =>
    request<null>('delete', '/wrong-book', { params: { member_id: MEMBER_ID } }),
  addWrongWord: (wordId: number) =>
    request<null>('post', `/wrong-book/${wordId}`, { params: { member_id: MEMBER_ID } }),
}
