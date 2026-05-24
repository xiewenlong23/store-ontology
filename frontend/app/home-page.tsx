'use client'

import { useCoAgent } from '@copilotkit/react-core'

export default function HomePage() {
  const { state: agentState, setState: setAgentState } = useCoAgent<{
    selected_store: string
  }>({
    name: 'default',
    initialState: { selected_store: 'store_001' },
  })

  const selectedStore = agentState.selected_store || 'store_001'

  return (
    <main className="main">
      <header className="header">
        <h1>🏪 门店临期商品管理</h1>
        <p className="subtitle">基于AI的智能门店临期商品管理系统</p>
      </header>
      <div className="content">
        <section className="section">
          <h2>📦 临期商品概览</h2>
          <p>当前门店: {selectedStore}</p>
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
          <h2>🎯 快捷操作</h2>
          <div className="button-group">
            <button className="btn" onClick={() => setAgentState({ selected_store: 'store_001' })}>
              门店1（北京朝阳店）
            </button>
            <button className="btn" onClick={() => setAgentState({ selected_store: 'store_002' })}>
              门店2（上海浦东店）
            </button>
          </div>
          <p style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            💡 共享状态 + 人工确认 — 切换门店 AI 自动感知，创建出清需确认
          </p>
        </section>
      </div>
    </main>
  )
}
