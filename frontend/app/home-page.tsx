'use client'

import { useCoAgent } from '@copilotkit/react-core'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useWorkspace } from './workspace-context'
import { useAuth } from './auth-context'

/**
 * 主页。
 *
 * v2（WP7）：
 * - workspace 选择器从 auth.memberships 派生（取代硬编码 KNOWN_WORKSPACES）
 * - 加 logout 按钮
 * - 门店选择暂保留 STORES 占位（从 /api/workspaces/{ws}/org-units 拉取留 v2.1）
 * - selected_store 双写：WorkspaceContext（→ X-Org-Unit-ID header）+ co-agent state（→ LLM 可见）
 */

// 占位：门店列表。完整实现从 API 拉取当前 workspace 的 OrgUnit(level=store)，留 v2.1。
const STORES = [
  { id: 'store_001', name: '北京朝阳店' },
  { id: 'store_002', name: '上海浦东店' },
]

export default function HomePage() {
  const router = useRouter()
  const { selectedStore, setSelectedStore, selectedWorkspace, setSelectedWorkspace, availableWorkspaces } = useWorkspace()
  const { logout, isAuthenticated } = useAuth()
  const { setState: setAgentState } = useCoAgent<{
    selected_store: string
  }>({
    name: 'default',
    initialState: { selected_store: 'store_001' },
  })

  const handleLogout = () => {
    logout()
    router.replace('/login')
  }

  const selectedName = STORES.find(s => s.id === selectedStore)?.name || selectedStore

  // 未登录由 layout 的 useEffect 处理重定向；此处避免渲染敏感内容
  if (!isAuthenticated) {
    return (
      <main className="main">
        <p style={{ padding: 24, color: '#666' }}>未登录，正在跳转登录页...</p>
      </main>
    )
  }

  return (
    <main className="main">
      <header className="header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1>🏪 门店临期商品管理</h1>
            <p className="subtitle">基于AI的智能门店临期商品管理系统</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link
              href="/dashboard"
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                background: '#3b82f6',
                color: '#fff',
                textDecoration: 'none',
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              📊 运营看板
            </Link>
            <button
              onClick={handleLogout}
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              🚪 退出
            </button>
          </div>
        </div>
      </header>
      <div className="content">
        <section className="section">
          <h2>📦 临期商品概览</h2>
          <p>当前门店: {selectedName}（{selectedStore}）</p>
          <p>使用AI对话来管理临期商品和创建出清任务</p>
        </section>
        <section className="section">
          <h2>💡 AI助手功能</h2>
          <ul>
            <li>查询临期商品列表 — AI 调用工具获取实时数据</li>
            <li>创建出清任务 — 需用户确认后执行（HITL）</li>
            <li>查看门店摘要</li>
            <li>了解折扣规则</li>
          </ul>
        </section>
        <section className="section">
          <h2>🗂️ 切换工作空间</h2>
          <div className="button-group">
            {availableWorkspaces.length === 0 && (
              <span style={{ color: '#999', fontSize: 14 }}>无可切换工作空间（ memberships 为空）</span>
            )}
            {availableWorkspaces.map(m => (
              <button
                key={m.workspace_name}
                className="btn"
                disabled={selectedWorkspace === m.workspace_name}
                onClick={() => setSelectedWorkspace(m.workspace_name)}
                title={m.workspace_display_name}
              >
                {m.workspace_display_name || m.workspace_name}
              </button>
            ))}
          </div>
          <p style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            💡 工作空间来自登录用户的 memberships（不同 workspace 本体/工具/skill 隔离）
          </p>
        </section>
        <section className="section">
          <h2>🎯 切换门店</h2>
          <div className="button-group">
            {STORES.map(s => (
              <button
                key={s.id}
                className="btn"
                disabled={selectedStore === s.id}
                onClick={() => {
                  setSelectedStore(s.id)
                  setAgentState({ selected_store: s.id })
                }}
              >
                {s.name}
              </button>
            ))}
          </div>
          <p style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            💡 共享状态 + 人工确认 — 切换门店 AI 自动感知，创建出清需确认
          </p>
        </section>
      </div>
    </main>
  )
}
