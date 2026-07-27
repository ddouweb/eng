import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '首页', icon: '🏠' } },
  { path: '/units', name: 'units', component: () => import('@/views/UnitsView.vue'), meta: { title: '单元管理', icon: '📚' } },
  { path: '/words', name: 'words', component: () => import('@/views/WordsView.vue'), meta: { title: '单词管理', icon: '🔤' } },
  { path: '/practice', name: 'practice', component: () => import('@/views/PracticeView.vue'), meta: { title: '练习', icon: '🎯' } },
  { path: '/stats', name: 'stats', component: () => import('@/views/StatsView.vue'), meta: { title: '统计', icon: '📊' } },
  { path: '/progress', name: 'progress', component: () => import('@/views/ProgressView.vue'), meta: { title: '进步趋势', icon: '📈' } },
  { path: '/plans', name: 'plans', component: () => import('@/views/PlansView.vue'), meta: { title: '学习计划', icon: '📅' } },
  { path: '/ai', name: 'ai', component: () => import('@/views/AiView.vue'), meta: { title: 'AI 助手', icon: '🤖' } },
  { path: '/wrong-book', name: 'wrong-book', component: () => import('@/views/WrongBookView.vue'), meta: { title: '错题本', icon: '📕' } },
  { path: '/search', name: 'search', component: () => import('@/views/SearchView.vue'), meta: { title: '单词查询', icon: '📖' } },
  { path: '/weekly-settlement', name: 'weekly-settlement', component: () => import('@/views/WeeklySettlementView.vue'), meta: { title: '本周结算', icon: '🌟' } },
]

const router = createRouter({ history: createWebHistory(), routes })

// 业务 401（token 失效）→ 跳登录页（带 redirect）。由 client 拦截器触发。
setUnauthorizedHandler(() => {
  const cur = router.currentRoute.value
  if (cur.name !== 'login') {
    router.push({ name: 'login', query: { redirect: cur.fullPath } })
  }
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthed) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthed) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
