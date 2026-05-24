'use client'

import { Inter } from 'next/font/google'
import { CopilotKit } from '@copilotkit/react-core'
import { CopilotChat } from '@copilotkit/react-ui'
import '@copilotkit/react-ui/styles.css'
import './globals.css'
import { useMemo } from 'react'

const inter = Inter({ subsets: ['latin'] })

function ProductCard({ text }: { text: string }) {
  return (
    <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0'}}>
      <strong>📋 Generative UI</strong>
      <pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>
        {text.substring(0, 800)}
      </pre>
    </div>
  )
}

function TaskCard({ text }: { text: string }) {
  const isError = text.includes('错误')
  return (
    <div style={{padding:12,background:isError?'#fef2f2':'#f0fdf4',borderRadius:8,border:`1px solid ${isError?'#ef4444':'#22c55e'}`,margin:'4px 0'}}>
      <strong>{isError ? '⚠️' : '✅'} {isError ? '操作失败' : '操作完成'}</strong>
      <pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>
        {text.substring(0, 500)}
      </pre>
    </div>
  )
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const renderToolCalls = useMemo(() => [
    {
      name: 'get_near_expiry_products',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#6366f1'}}>🔍 查询中...</div>
        if (status === 'complete' && result) {
          return <ProductCard text={typeof result === 'string' ? result : JSON.stringify(result)} />
        }
        return null as any
      },
    },
    {
      name: 'create_clearance_task',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#6366f1'}}>⚙️ 创建中...</div>
        if (status === 'complete' && result) {
          return <TaskCard text={typeof result === 'string' ? result : JSON.stringify(result)} />
        }
        return null as any
      },
    },
    {
      name: 'confirm_clearance_task',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#22c55e'}}>✅ 正在确认并创建出清任务...</div>
        if (status === 'complete' && result) {
          return (
            <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'2px solid #22c55e',margin:'4px 0'}}>
              <strong>✅ 出清任务已确认</strong>
              <pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>
                {typeof result === 'string' ? result : JSON.stringify(result)}
              </pre>
            </div>
          )
        }
        return null as any
      },
    },
    {
      name: 'query_entity',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#6366f1'}}>🔍 查询 {args?.entity_type}...</div>
        if (status === 'complete' && result) {
          return (
            <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0'}}>
              <strong>📊 查询结果</strong>
              <pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>
                {typeof result === 'string' ? result : JSON.stringify(result)}
              </pre>
            </div>
          )
        }
        return null as any
      },
    },
    {
      name: 'get_store_summary',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#6366f1'}}>📊 获取门店摘要...</div>
        if (status === 'complete' && result) {
          return (
            <div style={{padding:12,background:'#fefce8',borderRadius:8,border:'1px solid #eab308',margin:'4px 0'}}>
              <strong>🏪 门店摘要</strong>
              <pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>
                {typeof result === 'string' ? result : JSON.stringify(result)}
              </pre>
            </div>
          )
        }
        return null as any
      },
    },
    {
      name: 'create_entity',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#22c55e'}}>➕ 创建中...</div>
        if (status === 'complete' && result) {
          return <div style={{padding:10,background:'#f0fdf4',borderRadius:8}}>{String(result)}</div>
        }
        return null as any
      },
    },
    {
      name: 'update_entity',
      render: ({ status, result }: any) => {
        if (status === 'executing') return <div style={{padding:10,color:'#f59e0b'}}>✏️ 更新中...</div>
        if (status === 'complete' && result) {
          return <div style={{padding:10,background:'#fefce8',borderRadius:8}}>{String(result)}</div>
        }
        return null as any
      },
    },
  ], [])

  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          agent="default"
          renderToolCalls={renderToolCalls as any}
        >
          <div className="golden-layout">
            <div className="golden-left">
              {children}
            </div>
            <div className="golden-right">
              <CopilotChat />
            </div>
          </div>
        </CopilotKit>
      </body>
    </html>
  )
}
