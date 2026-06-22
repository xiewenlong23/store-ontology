'use client'

import { useState, FormEvent, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '../auth-context'

/**
 * v2 登录页（设计文档 §5 WP7）。
 *
 * 用户名 + 密码 → 调 /api/auth/login → 存 token → 跳首页。
 * 实名制：用户名是工号/手机号，跨 workspace 一致；后端扫描所有 workspace 验证。
 */
export default function LoginPage() {
  const router = useRouter()
  const { login, isAuthenticated } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // 已登录直接跳首页
  useEffect(() => {
    if (isAuthenticated) router.replace('/')
  }, [isAuthenticated, router])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const result = await login(username, password)
    setLoading(false)
    if (result.ok) {
      router.replace('/')
    } else {
      setError(result.error || '登录失败')
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#f5f5f5',
      fontFamily: 'system-ui, sans-serif',
    }}>
      <form
        onSubmit={handleSubmit}
        style={{
          background: 'white',
          padding: '32px',
          borderRadius: '12px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          width: '320px',
        }}
      >
        <h1 style={{ margin: '0 0 24px', fontSize: '20px', color: '#333' }}>
          OntologyAgent 登录
        </h1>

        <div style={{ marginBottom: '16px' }}>
          <label
            htmlFor="username"
            style={{ display: 'block', fontSize: '13px', color: '#666', marginBottom: '4px' }}
          >
            用户名（工号/手机号）
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            autoFocus
            style={{
              width: '100%', padding: '8px 12px', fontSize: '14px',
              border: '1px solid #ddd', borderRadius: '6px', boxSizing: 'border-box',
            }}
          />
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label
            htmlFor="password"
            style={{ display: 'block', fontSize: '13px', color: '#666', marginBottom: '4px' }}
          >
            密码
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{
              width: '100%', padding: '8px 12px', fontSize: '14px',
              border: '1px solid #ddd', borderRadius: '6px', boxSizing: 'border-box',
            }}
          />
        </div>

        {error && (
          <div style={{
            padding: '8px 12px', marginBottom: '16px', background: '#fef2f2',
            border: '1px solid #ef4444', borderRadius: '6px',
            color: '#dc2626', fontSize: '13px',
          }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: '100%', padding: '10px', fontSize: '14px',
            background: loading ? '#aaa' : '#2563eb', color: 'white',
            border: 'none', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? '登录中...' : '登录'}
        </button>

        <div style={{
          marginTop: '16px', fontSize: '12px', color: '#999', textAlign: 'center',
        }}>
          首次启动：用户名 <code>admin</code>，密码见 INITIAL_ADMIN_PASSWORD 环境变量（默认 admin123）
        </div>
      </form>
    </div>
  )
}
