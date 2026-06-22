import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { serversApi } from '../api/client'

interface ServerInfo {
  id: string
  name: string
  host: string
  port: number
  is_default: boolean
}

interface ServerState {
  servers: ServerInfo[]
  selectedId: string | null
  loading: boolean
  loaded: boolean
  fetchServers: () => Promise<void>
  selectServer: (id: string | null) => void
  reset: () => void
}

/**
 * Global store for the currently-selected ProxySQL instance.
 *
 * Before this existed the frontend hardcoded the literal "default" as the
 * server_id everywhere, which broke multi-instance management. Pages now
 * read `useServerStore((s) => s.selectedId)` (falling back to the default
 * server when nothing has been explicitly chosen).
 */
export const useServerStore = create<ServerState>()(
  persist(
    (set, get) => ({
      servers: [],
      selectedId: null,
      loading: false,
      loaded: false,

      fetchServers: async () => {
        if (get().loading) return
        set({ loading: true })
        try {
          const resp = await serversApi.list()
          const servers: ServerInfo[] = (resp.data || []).map((s: any) => ({
            id: s.id,
            name: s.name,
            host: s.host,
            port: s.port,
            is_default: s.is_default,
          }))
          const prevSelected = get().selectedId
          const stillExists = servers.some((s) => s.id === prevSelected)
          // Pick the previously selected server if it still exists, otherwise
          // fall back to the marked default, otherwise the first server.
          const nextSelected = stillExists
            ? prevSelected
            : servers.find((s) => s.is_default)?.id || servers[0]?.id || null
          set({ servers, selectedId: nextSelected, loaded: true })
        } catch {
          set({ servers: [], loaded: true })
        } finally {
          set({ loading: false })
        }
      },

      selectServer: (id) => set({ selectedId: id }),

      reset: () => set({ servers: [], selectedId: null, loaded: false }),
    }),
    {
      name: 'proxysql-selected-server',
      // Only persist the selected id, not the (potentially stale) list.
      partialize: (state) => ({ selectedId: state.selectedId }),
    }
  )
)
