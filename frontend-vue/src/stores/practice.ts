import { defineStore } from 'pinia'

import { api } from '@/api/client'
import type { ApiResp, FinishResp, PracticeStartData } from '@/api/types'

// 练习会话级状态。results 用 Map<word_id>（batch 模式下 append 会与 questions 下标错位，
// Map 按 word_id 对齐结束页回顾与改判；后端 (session,word) 幂等保证首提交为准）。
interface ResultEntry {
  isCorrect: boolean
  userAnswer: string | null
}

interface SubmitFailure {
  sessionId: number
  wordId: number
  isCorrect: boolean
  userAnswer: string | null
  msg: string
}

export const usePracticeStore = defineStore('practice', {
  state: () => ({
    sessionId: null as number | null,
    mode: '',
    unitIds: [] as number[],
    questions: [] as PracticeStartData['questions'],
    idx: 0,
    results: new Map<number, ResultEntry>(),
    finished: false,
    finishData: null as FinishResp | null,
    finishError: null as string | null,
    submitFailures: [] as SubmitFailure[],
    fcAutoNext: false,
    fcDelay: 3.0,
  }),
  getters: {
    total: (s) => s.questions.length,
    inProgress: (s) => s.questions.length > 0 && s.idx < s.questions.length,
    isDone: (s) => s.questions.length > 0 && s.idx >= s.questions.length,
    hasAnswer: (s) => s.results.size > 0,
    currentQuestion: (s) => s.questions[s.idx] ?? null,
    localCorrect: (s) => [...s.results.values()].filter((r) => r.isCorrect).length,
  },
  actions: {
    async start(
      mode: string,
      unitIds: number[],
      count: number,
      taskType?: string,
    ): Promise<ApiResp<PracticeStartData>> {
      const r = await api.startPractice(mode, unitIds, count, taskType)
      if (r.code === 200) {
        this.sessionId = r.data.session_id
        this.mode = mode
        this.unitIds = unitIds
        this.questions = r.data.questions
        this.idx = 0
        this.results = new Map()
        this.finished = false
        this.finishData = null
        this.finishError = null
        this.submitFailures = []
      }
      return r
    },
    async submitOne(wordId: number, isCorrect: boolean, userAnswer?: string | null): Promise<void> {
      this.results.set(wordId, { isCorrect, userAnswer: userAnswer ?? null })
      if (this.sessionId == null) return
      const r = await api.submitAnswer(this.sessionId, wordId, isCorrect, userAnswer ?? null)
      if (r.code !== 200) {
        this.submitFailures.push({
          sessionId: this.sessionId,
          wordId,
          isCorrect,
          userAnswer: userAnswer ?? null,
          msg: r.message,
        })
      } else {
        // 服务端权威复判覆盖客户端判定（7 个客观模式客户端 is_correct 会被后端改判）
        this.results.set(wordId, { isCorrect: r.data.is_correct, userAnswer: userAnswer ?? null })
      }
    },
    setIdx(idx: number): void {
      this.idx = idx
    },
    async finish(): Promise<void> {
      if (this.finished || this.sessionId == null) return
      // 仅成功才置 finished，失败保留可重试（否则后端会话悬挂 in_progress、结束页无入口重试）
      const r = await api.finishPractice(this.sessionId)
      if (r.code === 200) {
        this.finishData = r.data
        this.finishError = null
        this.finished = true
      } else {
        this.finishError = r.message || '结束练习失败，请重试'
      }
    },
    // 返回是否改判成功（调用方据此决定 toast）；未提交词后端 404 → false，不再误报成功
    async rejudge(wordId: number, target: boolean): Promise<boolean> {
      if (this.sessionId == null) return false
      const r = await api.rejudgeAnswer(this.sessionId, wordId, target)
      if (r.code === 200) {
        const prev = this.results.get(wordId)
        this.results.set(wordId, { isCorrect: target, userAnswer: prev?.userAnswer ?? null })
        if (this.finishData) {
          this.finishData = {
            ...this.finishData,
            correct_count: r.data.correct_count,
            accuracy: r.data.accuracy,
          }
        }
        return true
      }
      return false
    },
    async retryAllSubmits(): Promise<void> {
      const fails = this.submitFailures
      this.submitFailures = []
      for (const f of fails) {
        const r = await api.submitAnswer(f.sessionId, f.wordId, f.isCorrect, f.userAnswer ?? null)
        if (r.code !== 200) {
          this.submitFailures.push(f)
        } else {
          // 服务端权威复判覆盖（与 submitOne 成功分支口径一致），否则回顾页/改判按钮残留失败前客户端判定
          this.results.set(f.wordId, {
            isCorrect: r.data.is_correct,
            userAnswer: f.userAnswer ?? null,
          })
        }
      }
    },
    clearSubmits(): void {
      this.submitFailures = []
    },
    restart(): void {
      this.sessionId = null
      this.mode = ''
      this.unitIds = []
      this.questions = []
      this.idx = 0
      this.results = new Map()
      this.finished = false
      this.finishData = null
      this.finishError = null
      this.submitFailures = []
    },
  },
})
