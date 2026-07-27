import { defineStore } from 'pinia'

import { api, TOKEN_KEY } from '@/api/client'

// token 双写：localStorage（client 拦截器读取）+ store（响应式，供路由守卫/UI）。
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) as string | null,
  }),
  getters: {
    isAuthed: (s) => !!s.token,
  },
  actions: {
    async login(username: string, password: string) {
      const r = await api.login(username, password)
      if (r.code === 200 && r.data?.token) this.token = r.data.token
      return r
    },
    logout() {
      api.logout()
      this.token = null
    },
  },
})
