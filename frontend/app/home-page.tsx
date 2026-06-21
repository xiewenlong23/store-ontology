'use client'

import { useCoAgent } from '@copilotkit/react-core'
import { useWorkspace } from './workspace-context'

/**
 * 门店选择。
 * selected_store 双写：
 * - WorkspaceContext（selectedStore）→ 供 CopilotKit headers prop 注入 X-Org-Unit-ID（后端按门店过滤）
 * - useCoAgent（co-agent state）→ 供 LLM 读当前门店（走 request body，LLM 可见）
 * 见 docs/superpowers/specs/2026-06-21-v2-tenant-dynamic-design.md。
 */
const STORES = [
  { id: 'store_001', name: '北京朝阳店' },
  { id: 'store_002', name: '上海浦东店' },
]

export default function HomePage() {
  const { selectedStore, setSelectedStore } = useWorkspace()
  const { setState: setAgentState } = useCoAgent<{
    selected_store: string
  }>({
    name: 'default',
    initialState: { selected_store: 'store_001' },
  })

  const selectedName = STORES.find(s => s.id === selectedStore)?.name || selectedStore

  return (
    <main className="main">
      <header className="header">
        <h1>🏪 门店临期商品管理</h1>
        <p className="subtitle">基于AI的智能门店临期商品管理系统</p>
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
