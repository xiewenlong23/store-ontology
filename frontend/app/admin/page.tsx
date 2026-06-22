'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'

/**
 * v2 管理员数据浏览页（只读，WP7 配套）。
 *
 * 用途：admin 角色查看本 workspace 的 User / Role / PermissionGrant /
 * OrgUnit / Category 数据，验证权限体系配置。
 *
 * 数据源：GET /api/admin/customers/{ws}/data/{entity_type}
 * 后端权限：仅 system_admin 可访问；其他角色 → 403。
 *
 * 不做 CRUD（创建/编辑/删除）—— 那些走 Action（如 create_user Action），
 * 通过对话执行。本页只读浏览。
 */

const ADMIN_ENTITIES = [
  { type: 'User', label: '用户', domain: 'identity' },
  { type: 'Role', label: '角色', domain: 'identity' },
  { type: 'PermissionGrant', label: '权限授予', domain: 'identity' },
  { type: 'OrgUnit', label: '组织单元', domain: 'organization' },
  { type: 'Category', label: '品类', domain: 'category' },
  { type: 'Employee', label: '员工', domain: 'personnel' },
] as const

interface DataResponse {
  entity_type: string
  total: number
  items: any[]
}

export default function AdminPage() {
  const { selectedWorkspace } = useWorkspace()
  const { token, isAuthenticated } = useAuth()
  const [selected, setSelected] = useState<string>('User')
  const [data, setData] = useState<DataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated || !selectedWorkspace || !token) return
    setLoading(true)
    setError(null)
    fetch(`/api/admin/customers/${selectedWorkspace}/data/${selected}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async r => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(`${r.status}: ${body.detail || r.statusText}`)
        }
        return r.json()
      })
      .then(d => setData(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected, selectedWorkspace, token, isAuthenticated])

  if (!isAuthenticated) {
    return (
      <main style={{ padding: 24, color: '#666' }}>未登录，正在跳转登录页...</main>
    )
  }

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, fontFamily: 'system-ui' }}>
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>🛠️ 管理员数据浏览</h1>
          <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>
            workspace: <code>{selectedWorkspace}</code> · 只读（CRUD 走对话/Action）
          </p>
        </div>
        <Link
          href="/"
          style={{
            padding: '8px 16px', borderRadius: 6, background: '#3b82f6',
            color: '#fff', textDecoration: 'none', fontSize: 14, fontWeight: 500,
          }}
        >
          ← 返回首页
        </Link>
      </header>

      {/* 实体类型选择 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {ADMIN_ENTITIES.map(e => (
          <button
            key={e.type}
            onClick={() => setSelected(e.type)}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              border: `1px solid ${selected === e.type ? '#2563eb' : '#d1d5db'}`,
              background: selected === e.type ? '#2563eb' : '#fff',
              color: selected === e.type ? '#fff' : '#374151',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            {e.label} <span style={{ opacity: 0.6, fontSize: 11 }}>({e.domain})</span>
          </button>
        ))}
      </div>

      {/* 状态提示 */}
      {loading && <div style={{ padding: 12, color: '#666' }}>加载中...</div>}
      {error && (
        <div style={{
          padding: 12, background: '#fef2f2', border: '1px solid #ef4444',
          borderRadius: 6, color: '#dc2626', marginBottom: 12,
        }}>
          ⚠️ {error}
          {error.includes('403') && (
            <div style={{ marginTop: 6, fontSize: 13 }}>
              需 system_admin 角色。当前登录账号的 role 不是 system_admin。
            </div>
          )}
        </div>
      )}

      {/* 数据表 */}
      {data && !loading && !error && (
        <DataTable items={data.items} entityType={selected} />
      )}
    </main>
  )
}

function DataTable({ items, entityType }: { items: any[]; entityType: string }) {
  if (items.length === 0) {
    return <div style={{ padding: 12, color: '#999' }}>无数据</div>
  }
  // 取所有 keys 做表头（取前 8 个避免过宽）
  const allKeys = new Set<string>()
  items.forEach(it => Object.keys(it).forEach(k => allKeys.add(k)))
  const keys = Array.from(allKeys).slice(0, 8)

  return (
    <div>
      <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>
        共 {items.length} 条 {entityType}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse',
          background: '#fff', border: '1px solid #e5e7eb', fontSize: 13,
        }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              {keys.map(k => (
                <th key={k} style={{
                  padding: '8px 12px', textAlign: 'left',
                  borderBottom: '1px solid #e5e7eb', fontWeight: 600, color: '#374151',
                }}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 50).map((item, i) => (
              <tr key={item.id || i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                {keys.map(k => (
                  <td key={k} style={{ padding: '8px 12px', color: '#4b5563' }}>
                    {formatValue(item[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length > 50 && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
          只显示前 50 条（共 {items.length}）
        </div>
      )}
    </div>
  )
}

function formatValue(v: any): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v).slice(0, 60)
  if (typeof v === 'string' && v.length > 80) return v.slice(0, 80) + '...'
  return String(v)
}
