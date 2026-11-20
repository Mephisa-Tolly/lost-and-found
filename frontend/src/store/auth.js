/**
 * 登录态（V3.0）
 * 两个演示账号：user/user123（普通用户）、admin/admin123（管理员）
 * token 由后端签名，存在 localStorage，请求头带 Authorization: Bearer <token>
 */
import { defineStore } from 'pinia'
import request from '@/api/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('lf_token') || '',
    username: localStorage.getItem('lf_username') || '',
    role: localStorage.getItem('lf_role') || '', // 'user' | 'admin'
    loading: false,
  }),

  getters: {
    isLogged: (s) => !!s.token,
    isAdmin: (s) => s.role === 'admin',
    isUser: (s) => s.role === 'user',
    roleName: (s) => (s.role === 'admin' ? '管理员' : s.role === 'user' ? '普通用户' : ''),
  },

  actions: {
    async login(username, password) {
      this.loading = true
      try {
        const data = await request.post('/auth/login', { username, password })
        this.token = data.token
        this.username = data.username
        this.role = data.role
        localStorage.setItem('lf_token', data.token)
        localStorage.setItem('lf_username', data.username)
        localStorage.setItem('lf_role', data.role)
        return data
      } finally {
        this.loading = false
      }
    },

    /** 启动时校验 token 是否还有效（后端重启后旧 token 会失效） */
    async verify() {
      if (!this.token) return false
      try {
        await request.get('/auth/me')
        return true
      } catch {
        this.logout()
        return false
      }
    },

    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem('lf_token')
      localStorage.removeItem('lf_username')
      localStorage.removeItem('lf_role')
    },
  },
})
