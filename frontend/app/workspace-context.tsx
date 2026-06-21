'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

const WORKSPACE_STORAGE_KEY = 'store-ontology:selected-workspace'
const STORE_STORAGE_KEY = 'store-ontology:selected-store'

const KNOWN_WORKSPACES = ['jjy', 'customerA', 'retail'] as const
export type WorkspaceName = (typeof KNOWN_WORKSPACES)[number]

function isWorkspaceName(v: string | null): v is WorkspaceName {
  return v !== null && (KNOWN_WORKSPACES as readonly string[]).includes(v)
}

interface WorkspaceState {
  selectedWorkspace: WorkspaceName
  setSelectedWorkspace: (ws: WorkspaceName) => void
  selectedStore: string
  setSelectedStore: (store: string) => void
  availableWorkspaces: readonly WorkspaceName[]
}

const WorkspaceContext = createContext<WorkspaceState | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [selectedWorkspace, _setSelectedWorkspace] = useState<WorkspaceName>('jjy')
  const [selectedStore, _setSelectedStore] = useState('store_001')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const savedWs = window.localStorage.getItem(WORKSPACE_STORAGE_KEY)
    if (isWorkspaceName(savedWs)) _setSelectedWorkspace(savedWs)
    const savedStore = window.localStorage.getItem(STORE_STORAGE_KEY)
    if (savedStore) _setSelectedStore(savedStore)
  }, [])

  const setSelectedWorkspace = (ws: WorkspaceName) => {
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
        availableWorkspaces: KNOWN_WORKSPACES,
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
