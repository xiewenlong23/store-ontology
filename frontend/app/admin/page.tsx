'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '../auth-context'
import { OntologyEditor } from './ontology-editor'
import { DataBrowser } from './data-browser'

/**
 * v2 管理员页（WP7-WP9）。
 *
 * 两个 tab：
 * - 数据浏览（只读，原 admin/page.tsx 逻辑，搬到 data-browser.tsx）
 * - 本体编辑（CRUD：Object/Link/Action Type，全字段表单，WP9 新增）
 */

export default function AdminPage() {
  const { isAuthenticated } = useAuth()
  const [tab, setTab] = useState<'data' | 'ontology'>('data')

  if (!isAuthenticated) {
    return (
      <main style={{ padding: 24, color: '#666' }}>未登录，正在跳转登录页...</main>
    )
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, fontFamily: 'system-ui' }}>
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>🛠️ 管理员控制台</h1>
          <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>
            数据浏览（只读）· 本体编辑（Object/Link/Action Type CRUD）
          </p>
        </div>
        <Link href="/" style={{
          padding: '8px 16px', borderRadius: 6, background: '#3b82f6',
          color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 500,
        }}>← 返回首页</Link>
      </header>

      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        {(['data', 'ontology'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 18px', borderRadius: 6,
            border: `1px solid ${tab === t ? '#2563eb' : '#d1d5db'}`,
            background: tab === t ? '#2563eb' : '#fff',
            color: tab === t ? '#fff' : '#374151',
            cursor: 'pointer', fontSize: 14, fontWeight: 500,
          }}>
            {t === 'data' ? '📊 数据浏览' : '🧱 本体编辑'}
          </button>
        ))}
      </div>

      {tab === 'data' ? <DataBrowser /> : <OntologyEditor />}
    </main>
  )
}
