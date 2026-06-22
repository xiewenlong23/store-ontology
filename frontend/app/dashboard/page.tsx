'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useWorkspace } from '../workspace-context'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8123'

interface Metrics {
  tasks: { total: number; by_status: Record<string, number> }
  near_expiry: { total: number; by_status: Record<string, number> }
}

interface Todo {
  id: string
  task_type: string
  target_id: string
  store_id: string
  status: string
  discount_percent: number
  planned_quantity: number
  sold_quantity: number
  created_at: string
}

const STATUS_LABELS: Record<string, string> = {
  created: '已创建',
  pending_approval: '待审批',
  approved: '已审批',
  accepted: '已接单',
  in_progress: '进行中',
  completed: '已完成',
  scrapped: '已报损',
  expiring: '临期中',
  clearance: '出清中',
  sold_out: '已售罄',
  expired: '已过期',
}

const STATUS_COLORS: Record<string, string> = {
  created: '#6b7280',
  pending_approval: '#f59e0b',
  approved: '#3b82f6',
  accepted: '#3b82f6',
  in_progress: '#8b5cf6',
  completed: '#22c55e',
  scrapped: '#ef4444',
}

export default function DashboardPage() {
  const { selectedWorkspace, setSelectedWorkspace, availableWorkspaces } = useWorkspace()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [todos, setTodos] = useState<Todo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      fetch(`${API_BASE}/api/dashboard/${selectedWorkspace}/metrics`, { headers: { 'X-Workspace': selectedWorkspace } }).then(r => r.json()),
      fetch(`${API_BASE}/api/dashboard/${selectedWorkspace}/todos`, { headers: { 'X-Workspace': selectedWorkspace } }).then(r => r.json()),
    ]).then(([m, t]) => {
      setMetrics(m)
      setTodos(t.todos || [])
      setLoading(false)
    }).catch(e => {
      setError(e.message)
      setLoading(false)
    })
  }, [selectedWorkspace])

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>
  if (error) return <div style={{ padding: 40, color: '#ef4444' }}>加载失败: {error}</div>

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, fontFamily: 'system-ui' }}>
      <header style={{ marginBottom: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ marginBottom: 8 }}>
            <Link href="/" style={{ color: '#3b82f6', textDecoration: 'none', fontSize: 13 }}>← 返回首页</Link>
          </div>
          <h1 style={{ fontSize: 28, margin: 0 }}>📊 运营看板</h1>
          <p style={{ color: '#666', marginTop: 8 }}>跨域 KPI 指标 + 待办事项</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label htmlFor="dashboard-workspace-switcher" style={{ fontSize: 13, color: '#6b7280' }}>Workspace:</label>
          <select
            id="dashboard-workspace-switcher"
            value={selectedWorkspace}
            onChange={(e) => setSelectedWorkspace(e.target.value as typeof selectedWorkspace)}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid #d1d5db',
              background: '#fff',
              fontSize: 14,
            }}
          >
            {availableWorkspaces.map((m) => (
              <option key={m.workspace_name} value={m.workspace_name}>
                {m.workspace_display_name || m.workspace_name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* 指标卡 */}
      <section style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 20, marginBottom: 16 }}>📈 指标卡</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
          {metrics && (
            <>
              <MetricCard title="出清任务总数" value={metrics.tasks.total} color="#3b82f6" />
              {Object.entries(metrics.tasks.by_status).map(([status, count]) => (
                <MetricCard
                  key={status}
                  title={`任务·${STATUS_LABELS[status] || status}`}
                  value={count}
                  color={STATUS_COLORS[status] || '#6b7280'}
                />
              ))}
              <MetricCard title="临期商品总数" value={metrics.near_expiry.total} color="#f59e0b" />
              {Object.entries(metrics.near_expiry.by_status).map(([status, count]) => (
                <MetricCard
                  key={status}
                  title={`商品·${STATUS_LABELS[status] || status}`}
                  value={count}
                  color={STATUS_COLORS[status] || '#6b7280'}
                />
              ))}
            </>
          )}
        </div>
      </section>

      {/* 待办流 */}
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 16 }}>📋 待办事项 ({todos.length})</h2>
        {todos.length === 0 ? (
          <p style={{ color: '#22c55e', padding: 16, background: '#f0fdf4', borderRadius: 8 }}>
            ✅ 暂无待办
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {todos.map(todo => (
              <div key={todo.id} style={{
                padding: 16, borderRadius: 8, border: '1px solid #e5e7eb',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{todo.id}</span>
                  <span style={{ color: '#666', marginLeft: 12 }}>
                    目标: {todo.target_id} · 门店: {todo.store_id}
                  </span>
                  <span style={{ color: '#666', marginLeft: 12 }}>
                    售出 {todo.sold_quantity}/{todo.planned_quantity}
                  </span>
                </div>
                <span style={{
                  padding: '4px 12px', borderRadius: 12, fontSize: 13,
                  background: (STATUS_COLORS[todo.status] || '#6b7280') + '20',
                  color: STATUS_COLORS[todo.status] || '#6b7280',
                }}>
                  {STATUS_LABELS[todo.status] || todo.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

function MetricCard({ title, value, color }: { title: string; value: number; color: string }) {
  return (
    <div style={{
      padding: 20, borderRadius: 12, border: '1px solid #e5e7eb',
      background: '#fff', textAlign: 'center',
    }}>
      <div style={{ fontSize: 32, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{title}</div>
    </div>
  )
}
