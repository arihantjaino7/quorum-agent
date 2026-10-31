import { createContext, useContext } from 'react'

export interface AppState {
  project: string
  setProject: (project: string) => void
  theme: 'light' | 'dark'
  toggleTheme: () => void
  notify: (message: string) => void
}
export const AppContext = createContext<AppState | null>(null)
export function useApp() {
  const value = useContext(AppContext)
  if (!value) throw new Error('Quorum app provider is missing')
  return value
}
