'use client'

import { createContext, useContext, useState, ReactNode } from 'react'

interface WorkspaceState {
  selectedStore: string
  setSelectedStore: (store: string) => void
}

const WorkspaceContext = createContext<WorkspaceState | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [selectedStore, setSelectedStore] = useState('store_001')
  return (
    <WorkspaceContext.Provider value={{ selectedStore, setSelectedStore }}>
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
