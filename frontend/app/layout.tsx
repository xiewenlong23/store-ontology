'use client'

import { Inter } from 'next/font/google'
import { CopilotKit } from '@copilotkit/react-core'
import { CopilotChat } from '@copilotkit/react-ui'
import '@copilotkit/react-ui/styles.css'
import './globals.css'
import { Fragment, ReactNode, useMemo } from 'react'
import { WorkspaceProvider, useWorkspace } from './workspace-context'

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

function AppWithWorkspace({
  children,
}: {
  children: React.ReactNode
}) {
  const { selectedStore } = useWorkspace()
  // 通用：从工具返回文本中提取 JSON 数据
  const extractData = (result: any) => {
    const str = typeof result === 'string' ? result : JSON.stringify(result);
    const match = str.match(/<!--COPILOTKIT_DATA-->\n?([\s\S]*?)\n?<!--\/COPILOTKIT_DATA-->/);
    if (match) {
      try { return JSON.parse(match[1]); } catch { return null; }
    }
    return null;
  };

  const renderToolCalls = useMemo(() => [
    {
      name: 'query_near_expiry',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',textAlign:'center',color:'#3b82f6'}}>
            🔄 正在查询临期商品...
          </div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'near_expiry_list') {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.total === 0) {
            return <div style={{padding:16,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',color:'#166534',fontSize:13}}>✅ 暂无临期商品，库存状态良好</div>;
          }
          return (
            <div style={{margin:'4px 0'}}>
              <div style={{padding:'8px 12px',background:'#f8fafc',borderRadius:'8px 8px 0 0',border:'1px solid #e2e8f0',borderBottom:'none',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <span style={{fontWeight:600,color:'#1e293b'}}>📦 临期商品列表</span>
                <span style={{background:'#ef4444',color:'white',padding:'2px 8px',borderRadius:12,fontSize:12,fontWeight:600}}>{data.total} 件</span>
              </div>
              {data.items.map((item: any, idx: number) => {
                const progressPct = Math.min(100, Math.max(0, (item.days_left / 14) * 100));
                const pColor = item.days_left <= 3 ? '#ef4444' : item.days_left <= 7 ? '#f59e0b' : '#22c55e';
                return (
                  <div key={item.id || idx} style={{padding:'10px 12px',background:'white',border:'1px solid #e2e8f0',borderTop:idx===0?'none':undefined,borderRadius:idx===data.items.length-1?'0 0 8px 8px':0}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                      <div>
                        <span style={{fontWeight:600,color:'#1e293b',fontSize:14}}>{item.product_name}</span>
                        <span style={{marginLeft:6,fontSize:12,color:'#64748b'}}>{item.brand} · {item.category}</span>
                      </div>
                      <span style={{background:item.tier_color,color:'white',padding:'2px 8px',borderRadius:10,fontSize:11,fontWeight:600}}>{item.tier_label} {item.discount_percent}%off</span>
                    </div>
                    <div style={{display:'flex',gap:16,fontSize:12,color:'#64748b',marginBottom:6}}>
                      <span>📦 库存: <strong style={{color:'#1e293b'}}>{item.stock_quantity}{item.unit}</strong></span>
                      <span>批次: {item.batch_no}</span>
                    </div>
                    <div style={{marginBottom:4}}>
                      <div style={{display:'flex',justifyContent:'space-between',fontSize:11,color:'#64748b',marginBottom:3}}>
                        <span>生产: {item.production_date}</span>
                        <span style={{color:pColor,fontWeight:600}}>剩 {item.days_left} 天 · {item.expiry_date} 到期</span>
                      </div>
                      <div style={{background:'#f1f5f9',borderRadius:4,height:6,overflow:'hidden'}}>
                        <div style={{width:`${progressPct}%`,height:'100%',background:pColor,borderRadius:4,transition:'width 0.3s'}} />
                      </div>
                    </div>
                    <div style={{display:'flex',alignItems:'baseline',gap:8,marginTop:4}}>
                      <span style={{fontSize:16,fontWeight:700,color:pColor}}>¥{item.discounted_price}</span>
                      <span style={{fontSize:12,color:'#94a3b8',textDecoration:'line-through'}}>原价 ¥{item.original_price}</span>
                      <span style={{marginLeft:'auto',fontSize:11,color:'#64748b'}}>{item.store_id}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }
        return null as any;
      },
    },
    {
      name: 'query_task',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',textAlign:'center',color:'#3b82f6'}}>🔄 正在查询任务...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'task_list') {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.total === 0) {
            return <div style={{padding:16,background:'#f8fafc',borderRadius:8,border:'1px solid #e2e8f0',margin:'4px 0',color:'#64748b',fontSize:13}}>📋 暂无任务记录</div>;
          }
          const typeLabels: Record<string,string> = {clearance:'出清',transfer:'调拨',restock:'补货',unknown:'其他'};
          return (
            <div style={{margin:'4px 0'}}>
              <div style={{padding:'8px 12px',background:'#f8fafc',borderRadius:'8px 8px 0 0',border:'1px solid #e2e8f0',borderBottom:'none',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <span style={{fontWeight:600,color:'#1e293b'}}>📋 任务列表</span>
                <span style={{background:'#6366f1',color:'white',padding:'2px 8px',borderRadius:12,fontSize:12,fontWeight:600}}>{data.total} 个任务</span>
              </div>
              {data.items.map((task: any, idx: number) => (
                <div key={task.id || idx} style={{padding:'10px 12px',background:'white',border:'1px solid #e2e8f0',borderTop:idx===0?'none':undefined,borderRadius:idx===data.items.length-1?'0 0 8px 8px':0}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                    <div style={{display:'flex',alignItems:'center',gap:8}}>
                      <span style={{fontWeight:600,color:'#1e293b',fontSize:13}}>{typeLabels[task.type] || task.type}</span>
                      <span style={{background:task.status_color,color:'white',padding:'2px 8px',borderRadius:10,fontSize:11,fontWeight:600}}>{task.status_label}</span>
                    </div>
                    <span style={{fontSize:11,color:'#94a3b8'}}>{task.id}</span>
                  </div>
                  <div style={{display:'flex',gap:16,fontSize:12,color:'#64748b'}}>
                    <span>目标: {task.target_id}</span>
                    <span>门店: {task.store_id}</span>
                    {task.discount ? <span>折扣: {task.discount}%</span> : null}
                  </div>
                  {task.created_at && <div style={{fontSize:11,color:'#94a3b8',marginTop:4}}>创建于: {task.created_at.split('T')[0]}</div>}
                </div>
              ))}
            </div>
          );
        }
        return null as any;
      },
    },
    {
      name: 'execute_action',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',textAlign:'center',color:'#3b82f6'}}>⚙️ 正在生成操作预览...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'action_preview') {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (!data.valid) {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',color:'#dc2626',fontSize:13}}>⚠️ {data.error}</div>;
          }
          const actionColors: Record<string,string> = {clearance:'#ef4444',transfer:'#3b82f6',restock:'#22c55e'};
          const ac = actionColors[data.action_type] || '#6366f1';
          return (
            <div style={{margin:'4px 0'}}>
              <div style={{padding:'8px 12px',background:'#fefce8',borderRadius:'8px 8px 0 0',border:'1px solid #f59e0b',borderBottom:'none',display:'flex',alignItems:'center',gap:8}}>
                <span style={{fontSize:16}}>⚠️</span>
                <span style={{fontWeight:600,color:'#92400e'}}>操作预览 — 请确认</span>
              </div>
              <div style={{padding:'12px',background:'white',border:'1px solid #f59e0b',borderTop:'none',borderRadius:'0 0 8px 8px'}}>
                <div style={{marginBottom:8}}>
                  <span style={{display:'inline-block',background:ac,color:'white',padding:'2px 10px',borderRadius:10,fontSize:12,fontWeight:600}}>{data.action_label}</span>
                </div>
                <table style={{width:'100%',fontSize:13,borderCollapse:'collapse'}}>
                  <tbody>
                    <tr><td style={{color:'#64748b',padding:'2px 0'}}>操作目标</td><td style={{fontWeight:500,padding:'2px 8px',textAlign:'right'}}>{data.target_name}</td></tr>
                    <tr><td style={{color:'#64748b',padding:'2px 0'}}>目标ID</td><td style={{padding:'2px 8px',textAlign:'right',fontSize:12}}>{data.target_id}</td></tr>
                    <tr><td style={{color:'#64748b',padding:'2px 0'}}>门店</td><td style={{padding:'2px 8px',textAlign:'right'}}>{data.store_name} ({data.store_id})</td></tr>
                    <tr><td style={{color:'#64748b',padding:'2px 0'}}>负责人</td><td style={{padding:'2px 8px',textAlign:'right'}}>{data.assignee_id || '-'}</td></tr>
                    {data.params?.discount && <tr><td style={{color:'#64748b',padding:'2px 0'}}>折扣</td><td style={{padding:'2px 8px',textAlign:'right',fontWeight:600,color:'#dc2626'}}>{data.params.discount}%</td></tr>}
                    {data.params?.quantity && <tr><td style={{color:'#64748b',padding:'2px 0'}}>数量</td><td style={{padding:'2px 8px',textAlign:'right'}}>{data.params.quantity}</td></tr>}
                  </tbody>
                </table>
                <div style={{marginTop:10,padding:'8px 12px',background:'#fef9c3',borderRadius:6,fontSize:12,color:'#92400e'}}>
                  💡 回复"确认"、"好的"或"可以"来完成操作
                </div>
              </div>
            </div>
          );
        }
        return null as any;
      },
    },
    {
      name: 'confirm_action',
      render: ({ status, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',textAlign:'center',color:'#166534'}}>✅ 正在执行操作...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'action_result') {
            return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'2px solid #22c55e',margin:'4px 0'}}><strong>✅ 操作完成</strong><pre style={{fontSize:12,whiteSpace:'pre-wrap',margin:'4px 0 0'}}>{typeof result === 'string' ? result : JSON.stringify(result)}</pre></div>;
          }
          if (!data.success) {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'2px solid #ef4444',margin:'4px 0',color:'#dc2626'}}><strong>⚠️ 操作失败</strong><div style={{marginTop:6,fontSize:13}}>{data.error}</div></div>;
          }
          return (
            <div style={{padding:16,background:'#f0fdf4',borderRadius:8,border:'2px solid #22c55e',margin:'4px 0'}}>
              <div style={{fontWeight:700,color:'#166534',fontSize:14,marginBottom:8}}>✅ 操作已创建</div>
              <table style={{fontSize:13,borderCollapse:'collapse'}}>
                <tbody>
                  <tr><td style={{color:'#64748b',padding:'2px 0'}}>任务ID</td><td style={{padding:'2px 8px',fontWeight:500}}>{data.task_id}</td></tr>
                  <tr><td style={{color:'#64748b',padding:'2px 0'}}>操作类型</td><td style={{padding:'2px 8px'}}>{data.action_label}</td></tr>
                  <tr><td style={{color:'#64748b',padding:'2px 0'}}>操作目标</td><td style={{padding:'2px 8px'}}>{data.target_name}</td></tr>
                  <tr><td style={{color:'#64748b',padding:'2px 0'}}>门店</td><td style={{padding:'2px 8px'}}>{data.store_id}</td></tr>
                </tbody>
              </table>
            </div>
          );
        }
        return null as any;
      },
    },
    {
      name: 'query_entity',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',textAlign:'center',color:'#3b82f6'}}>🔄 正在查询实体...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data) {
            return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.type === 'entity_detail') {
            const d = data.data;
            return (
              <div style={{margin:'4px 0'}}>
                <div style={{padding:'8px 12px',background:'#f8fafc',borderRadius:'8px 8px 0 0',border:'1px solid #e2e8f0',borderBottom:'none'}}>
                  <span style={{fontWeight:600,color:'#1e293b'}}>📊 {data.entity_type} 详情</span>
                  <span style={{marginLeft:8,fontSize:12,color:'#64748b'}}>{data.entity_id}</span>
                </div>
                <div style={{padding:'12px',background:'white',border:'1px solid #e2e8f0',borderTop:'none',borderRadius:'0 0 8px 8px'}}>
                  <div style={{display:'grid',gridTemplateColumns:'auto 1fr',gap:'4px 12px',fontSize:13}}>
                    {Object.entries(d).filter(([k]) => k !== 'id').map(([k, v]) => (
                      <Fragment key={k}><span style={{color:'#64748b'}}>{k}</span><span style={{fontWeight:500}}>{String(v)}</span></Fragment>
                    ))}
                  </div>
                </div>
              </div>
            );
          }
          if (data.type === 'entity_list') {
            if (data.total === 0) {
              return <div style={{padding:16,background:'#f8fafc',borderRadius:8,border:'1px solid #e2e8f0',margin:'4px 0',color:'#64748b',fontSize:13}}>未找到 {data.entity_type} 记录</div>;
            }
            return (
              <div style={{margin:'4px 0'}}>
                <div style={{padding:'8px 12px',background:'#f8fafc',borderRadius:'8px 8px 0 0',border:'1px solid #e2e8f0',borderBottom:'none',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{fontWeight:600,color:'#1e293b'}}>📊 {data.label_zh || data.entity_type}</span>
                  <span style={{background:'#3b82f6',color:'white',padding:'2px 8px',borderRadius:12,fontSize:12,fontWeight:600}}>{data.total} 条</span>
                </div>
                {data.items.map((item: any, idx: number) => (
                  <div key={item.id || idx} style={{padding:'8px 12px',background:'white',border:'1px solid #e2e8f0',borderTop:idx===0?'none':undefined,borderRadius:idx===data.items.length-1?'0 0 8px 8px':0}}>
                    <div style={{fontWeight:600,color:'#1e293b',fontSize:13,marginBottom:4}}>{item.id}</div>
                    <div style={{display:'flex',flexWrap:'wrap',gap:'2px 12px',fontSize:12}}>
                      {Object.entries(item.fields || {}).map(([k, v]) => (
                        <span key={k}><strong style={{color:'#64748b'}}>{k}:</strong> {String(v)}</span>
                      ))}
                    </div>
                  </div>
                ))}
                {data.has_more && <div style={{padding:'6px 12px',background:'#f8fafc',border:'1px solid #e2e8f0',borderTop:'none',borderRadius:'0 0 8px 8px',fontSize:12,color:'#64748b',textAlign:'center'}}>...还有更多记录</div>}
              </div>
            );
          }
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
        }
        return null as any;
      },
    },
    {
      name: 'traverse_relation',
      render: ({ status, args, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#eff6ff',borderRadius:8,border:'1px solid #3b82f6',margin:'4px 0',textAlign:'center',color:'#3b82f6'}}>🔄 正在查询关系...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'relation_result') {
            return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.total === 0) {
            return <div style={{padding:16,background:'#f8fafc',borderRadius:8,border:'1px solid #e2e8f0',margin:'4px 0',color:'#64748b',fontSize:13}}>未找到 {data.relation_label} 关系</div>;
          }
          return (
            <div style={{margin:'4px 0'}}>
              <div style={{padding:'8px 12px',background:'#f8fafc',borderRadius:'8px 8px 0 0',border:'1px solid #e2e8f0',borderBottom:'none'}}>
                <span style={{fontWeight:600,color:'#1e293b'}}>🔗 {data.relation_label}</span>
                <span style={{marginLeft:8,fontSize:12,color:'#64748b'}}>{data.source_name || data.source_id} → {data.target_type}</span>
              </div>
              <div style={{padding:'10px 12px',background:'white',border:'1px solid #e2e8f0',borderTop:'none',borderRadius:'0 0 8px 8px'}}>
                {data.targets.map((t: any, idx: number) => (
                  <div key={t.id || idx} style={{display:'flex',alignItems:'center',gap:8,padding:'4px 0',borderBottom:idx<data.targets.length-1?'1px solid #f1f5f9':'none'}}>
                    <span style={{color:'#3b82f6'}}>→</span>
                    <span style={{fontWeight:500,color:'#1e293b',fontSize:13}}>{t.Name || t.id}</span>
                    <span style={{marginLeft:'auto',fontSize:11,color:'#94a3b8'}}>{t.id}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        }
        return null as any;
      },
    },
    {
      name: 'update_task',
      render: ({ status, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#fefce8',borderRadius:8,border:'1px solid #f59e0b',margin:'4px 0',textAlign:'center',color:'#92400e'}}>✏️ 正在更新任务...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'update_task_result') {
            return <div style={{padding:12,background:'#fefce8',borderRadius:8,border:'1px solid #f59e0b',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.success) {
            return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',color:'#166534',fontSize:13}}>✅ 已更新任务 {data.task_id}：{Object.entries(data.updated_fields || {}).map(([k,v])=>`${k}=${v}`).join(', ')}</div>;
          }
          return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',color:'#dc2626',fontSize:13}}>⚠️ {data.error}</div>;
        }
        return null as any;
      },
    },
    {
      name: 'create_entity',
      render: ({ status, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',textAlign:'center',color:'#166534'}}>➕ 正在创建实体...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'create_result') {
            return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.success) {
            return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',color:'#166534',fontSize:13}}>✅ 已创建 {data.entity_type}：{data.entity_id}</div>;
          }
          return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',color:'#dc2626',fontSize:13}}>⚠️ {data.error}</div>;
        }
        return null as any;
      },
    },
    {
      name: 'update_entity',
      render: ({ status, result }: any) => {
        if (status === 'executing') {
          return <div style={{padding:12,background:'#fefce8',borderRadius:8,border:'1px solid #f59e0b',margin:'4px 0',textAlign:'center',color:'#92400e'}}>✏️ 正在更新实体...</div>;
        }
        if (status === 'complete' && result) {
          const data = extractData(result);
          if (!data || data.type !== 'update_result') {
            return <div style={{padding:12,background:'#fefce8',borderRadius:8,border:'1px solid #f59e0b',margin:'4px 0',fontSize:13}}>{typeof result === 'string' ? result : JSON.stringify(result)}</div>;
          }
          if (data.success) {
            return <div style={{padding:12,background:'#f0fdf4',borderRadius:8,border:'1px solid #22c55e',margin:'4px 0',color:'#166534',fontSize:13}}>✅ 已更新 {data.entity_type} {data.entity_id}：{Object.entries(data.updated_fields || {}).map(([k,v])=>`${k}=${v}`).join(', ')}</div>;
          }
          return <div style={{padding:12,background:'#fef2f2',borderRadius:8,border:'1px solid #ef4444',margin:'4px 0',color:'#dc2626',fontSize:13}}>⚠️ {data.error}</div>;
        }
        return null as any;
      },
    },
  ], [])

  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="default"
      headers={() => ({
        'X-Workspace': 'customer_default',
        'X-Org-Unit-ID': selectedStore || '*',
      })}
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
  )
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <WorkspaceProvider>
          <AppWithWorkspace>{children}</AppWithWorkspace>
        </WorkspaceProvider>
      </body>
    </html>
  )
}
