'use client'

import { useState, useEffect } from 'react'
import { useWorkspace } from '../workspace-context'
import { useAuth } from '../auth-context'

const ADMIN_ENTITIES = [
  { type: 'User', label: '用户', domain: 'identity' },
  { type: 'Role', label: '角色', domain: 'identity' },
  { type: 'PermissionGrant', label: '权限授予', domain: 'identity' },
  { type: 'OrgUnit', label: '组织单元', domain: 'organization' },
  { type: 'Category', label: '品类', domain: 'category' },
  { type: 'Employee', label: '员工', domain: 'personnel' },
] as const

interface DataResponse { entity_type: string; total: number; items: any[] }

export function DataBrowser() {
  const { selectedWorkspace } = useWorkspace()
  const { token, isAuthenticated } = useAuth()
  const [selected, setSelected] = useState<string>('User')
  const [data, setData] = useState<DataResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated || !selectedWorkspace || !token) return
    setLoading(true); setError(null)
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

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {ADMIN_ENTITIES.map(e => (
          <button key={e.type} onClick={() => setSelected(e.type)} style={{
            padding: '6px 14px', borderRadius: 6,
            border: `1px solid ${selected === e.type ? '#2563eb' : '#d1d5db'}`,
            background: selected === e.type ? '#2563eb' : '#fff',
            color: selected === e.type ? '#fff' : '#374151',
            cursor: 'pointer', fontSize: 13,
          }}>{e.label} <span style={{ opacity: 0.6, fontSize: 11 }}>({e.domain})</span></button>
        ))}
      </div>
      {loading && <div style={{ padding: 12, color: '#666' }}>加载中...</div>}
      {error && (
        <div style={{
          padding: 12, background: '#fef2f2', border: '1px solid #ef4444',
          borderRadius: 6, color: '#dc2626', marginBottom: 12,
        }}>⚠️ {error}
          {error.includes('403') && (
            <div style={{ marginTop: 6, fontSize: 13 }}>需 system_admin 角色。</div>
          )}
        </div>
      )}
      {data && !loading && !error && <DataTable items={data.items} entityType={selected} />}
    </div>
  )
}

function DataTable({ items, entityType }: { items: any[]; entityType: string }) {
  if (items.length === 0) return <div style={{ padding: 12, color: '#999' }}>无数据</div>
  const allKeys = new Set<string>()
  items.forEach(it => Object.keys(it).forEach(k => allKeys.add(k)))
  const keys = Array.from(allKeys).slice(0, 8)
  return (
    <div>
      <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>共 {items.length} 条 {entityType}</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'collapse', background: '#fff',
          border: '1px solid #e5e7eb', fontSize: 13,
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
