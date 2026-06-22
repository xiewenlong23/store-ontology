'use client'

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

/**
 * v2 认证上下文（设计文档 §5 WP7）。
 *
 * 存储：
 * - token（access token，存 localStorage）
 * - refreshToken（存 localStorage）
 * - user：登录用户基本信息（user_id、username、display_name）
 * - memberships：用户有权限访问的 workspace 列表（每个含 workspace_name/role/org_unit 等）
 *
 * 行为：
 * - 无 token 时调用方应重定向到 /login
 * - fetch /me 验证 token 有效性（401 → 清 token + 跳登录）
 */

const TOKEN_KEY = 'store-ontology:token'
const REFRESH_TOKEN_KEY = 'store-ontology:refresh-token'

export interface Membership {
  workspace_name: string
  workspace_display_name: string
  user_id: string
  username: string
  display_name: string
  // role/org_unit_id 字段需后端 WP5+ 补充；当前 me endpoint 只返回 user 维度
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  memberships: Membership[]
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<{ ok: boolean; error?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)
  const [memberships, setMemberships] = useState<Membership[]>([])

  // 初始化：从 localStorage 读 token，若有则验有效性（fetch /me）
  useEffect(() => {
    if (typeof window === 'undefined') return
    const savedToken = window.localStorage.getItem(TOKEN_KEY)
    const savedRefresh = window.localStorage.getItem(REFRESH_TOKEN_KEY)
    if (savedToken) {
      setToken(savedToken)
      setRefreshToken(savedRefresh)
      // 异步验证 token（401 会清 token）
      fetch('/api/auth/me', { headers: { Authorization: `Bearer ${savedToken}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data || !data.authenticated) {
            // token 失效
            _clearTokens()
            setToken(null)
            setRefreshToken(null)
          }
        })
        .catch(() => { /* 网络错不强制清 token */ })
    }
  }, [])

  const _clearTokens = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(TOKEN_KEY)
      window.localStorage.removeItem(REFRESH_TOKEN_KEY)
    }
  }

  const login = useCallback(async (username: string, password: string) => {
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await resp.json()
      if (!data.success) {
        return { ok: false, error: data.error || '登录失败' }
      }
      setToken(data.token)
      setRefreshToken(data.refresh_token)
      setMemberships(data.memberships || [])
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(TOKEN_KEY, data.token)
        window.localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token)
      }
      return { ok: true }
    } catch (e: any) {
      return { ok: false, error: e?.message || '网络错误' }
    }
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setRefreshToken(null)
    setMemberships([])
    _clearTokens()
  }, [])

  return (
    <AuthContext.Provider
      value={{
        token,
        refreshToken,
        memberships,
        isAuthenticated: !!token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
