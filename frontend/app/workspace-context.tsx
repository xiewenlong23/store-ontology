'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useAuth, Membership } from './auth-context'

/**
 * v2 workspace 选择（设计文档 §5 WP7）。
 *
 * 改动：
 * - availableWorkspaces 从 auth.memberships 派生（取代硬编码 KNOWN_WORKSPACES）
 * - selectedStore 仍 localStorage 化（兼容），但建议从 API 拉（下一步）
 * - 无 memberships 时（未登录）回落空数组，组件层处理重定向
 */

const WORKSPACE_STORAGE_KEY = 'store-ontology:selected-workspace'
const STORE_STORAGE_KEY = 'store-ontology:selected-store'

interface WorkspaceState {
  selectedWorkspace: string
  setSelectedWorkspace: (ws: string) => void
  selectedStore: string
  setSelectedStore: (store: string) => void
  availableWorkspaces: Membership[]   // 从 memberships 派生
}

const WorkspaceContext = createContext<WorkspaceState | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { memberships } = useAuth()
  const [selectedWorkspace, _setSelectedWorkspace] = useState<string>('')
  const [selectedStore, _setSelectedStore] = useState('store_001')

  // 初始化：localStorage 缓存
  useEffect(() => {
    if (typeof window === 'undefined') return
    const savedWs = window.localStorage.getItem(WORKSPACE_STORAGE_KEY)
    if (savedWs) _setSelectedWorkspace(savedWs)
    const savedStore = window.localStorage.getItem(STORE_STORAGE_KEY)
    if (savedStore) _setSelectedStore(savedStore)
  }, [])

  // memberships 变化（登录后）：若当前 ws 不在 memberships，回落到第一个
  useEffect(() => {
    if (memberships.length === 0) return
    const valid = memberships.some(m => m.workspace_name === selectedWorkspace)
    if (!valid) {
      const first = memberships[0].workspace_name
      _setSelectedWorkspace(first)
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(WORKSPACE_STORAGE_KEY, first)
      }
    }
  }, [memberships, selectedWorkspace])

  const setSelectedWorkspace = (ws: string) => {
    _setSelectedWorkspace(ws)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(WORKSPACE_STORAGE_KEY, ws)
    }
  }

  const setSelectedStore = (store: string) => {
    _setSelectedStore(store)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORE_STORAGE_KEY, store)
    }
  }

  return (
    <WorkspaceContext.Provider
      value={{
        selectedWorkspace,
        setSelectedWorkspace,
        selectedStore,
        setSelectedStore,
        availableWorkspaces: memberships,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) {
    throw new Error('useWorkspace must be used within WorkspaceProvider')
  }
  return ctx
}
