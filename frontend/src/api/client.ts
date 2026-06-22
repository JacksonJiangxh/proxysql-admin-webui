import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach auth token + CSRF token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Attach CSRF token for state-changing requests.
  // The backend CSRFMiddleware uses the Double Submit Cookie pattern:
  // the token is read from the csrf_token cookie and sent back in the
  // X-CSRF-Token header.
  const method = (config.method || 'get').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = getCookie('csrf_token')
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }
  return config
})

// Helper: read a cookie value by name
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? decodeURIComponent(match[2]) : null
}

// Response interceptor: handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken && error.config && !error.config._retry) {
        error.config._retry = true
        try {
          const resp = await axios.post('/api/v1/auth/refresh', {}, {
            headers: { Authorization: `Bearer ${refreshToken}` }
          })
          localStorage.setItem('access_token', resp.data.access_token)
          localStorage.setItem('refresh_token', resp.data.refresh_token)
          error.config.headers.Authorization = `Bearer ${resp.data.access_token}`
          return apiClient(error.config)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      } else {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Wizard API
export const wizardApi = {
  getDefinitions: () => apiClient.get('/api/v1/wizards/definitions'),
  getDefinition: (wizardId: string) => apiClient.get(`/api/v1/wizards/definitions/${wizardId}`),
  preview: (wizardId: string, serverId: string, fields: Record<string, unknown>) =>
    apiClient.post('/api/v1/wizards/preview', { wizard_id: wizardId, server_id: serverId, fields }),
  execute: (wizardId: string, serverId: string, fields: Record<string, unknown>, options?: Record<string, unknown>) =>
    apiClient.post('/api/v1/wizards/execute', {
      wizard_id: wizardId,
      server_id: serverId,
      fields,
      options: options || { auto_apply: false, auto_save: false },
    }),
  getHistory: (serverId: string, limit?: number) =>
    apiClient.get(`/api/v1/wizards/history/${serverId}`, { params: { limit } }),
  lookupOptions: (serverId: string, wizardId: string, fieldName: string) =>
    apiClient.post('/api/v1/wizards/lookup-options', { server_id: serverId, wizard_id: wizardId, field_name: fieldName }),
}

// Template API
export const templateApi = {
  getTemplates: () => apiClient.get('/api/v1/wizards/templates'),
  getTemplate: (templateId: string) => apiClient.get(`/api/v1/wizards/templates/${templateId}`),
  getSteps: (templateId: string, architectureMode: string) =>
    apiClient.get(`/api/v1/wizards/templates/${templateId}/steps`, { params: { architecture_mode: architectureMode } }),
  preview: (data: {
    template_id: string
    server_id: string
    architecture_mode: string
    shared_values: Record<string, unknown>
    step_values: Record<string, Record<string, unknown>>
    skipped_steps: string[]
  }) => apiClient.post('/api/v1/wizards/templates/preview', data),
  execute: (data: {
    template_id: string
    server_id: string
    architecture_mode: string
    shared_values: Record<string, unknown>
    step_values: Record<string, Record<string, unknown>>
    skipped_steps: string[]
    options: Record<string, unknown>
  }) => apiClient.post('/api/v1/wizards/templates/execute', data),
}

// Dashboard API
export const dashboardApi = {
  getSnapshot: (serverId: string) => apiClient.get(`/api/v1/dashboard/${serverId}/snapshot`),
}

// Tables API
export const tablesApi = {
  list: (serverId: string) => apiClient.get(`/api/v1/${serverId}/tables`),
  getData: (serverId: string, tableName: string, params?: Record<string, unknown>) =>
    apiClient.get(`/api/v1/${serverId}/tables/${tableName}`, { params }),
  getSchema: (serverId: string, tableName: string, layer?: string) =>
    apiClient.get(`/api/v1/${serverId}/tables/${tableName}/schema`, { params: layer ? { layer } : {} }),
}

// Sync API
export const syncApi = {
  getStatus: (serverId: string) => apiClient.get(`/api/v1/sync/${serverId}/status`),
  apply: (serverId: string, tables?: string[]) => apiClient.post(`/api/v1/sync/${serverId}/apply`, tables),
  save: (serverId: string, tables?: string[]) => apiClient.post(`/api/v1/sync/${serverId}/save`, tables),
  discard: (serverId: string, tables?: string[]) => apiClient.post(`/api/v1/sync/${serverId}/discard`, tables),
  load: (serverId: string, tables?: string[]) => apiClient.post(`/api/v1/sync/${serverId}/load`, tables),
}

// Query API
export const queryApi = {
  execute: (serverId: string, sql: string, target?: string) =>
    apiClient.post(`/api/v1/query/${serverId}/execute`, { sql, target: target || 'admin' }),
  getSchema: (serverId: string) => apiClient.get(`/api/v1/query/${serverId}/schema`),
}

// Servers API
export const serversApi = {
  list: () => apiClient.get('/api/v1/servers'),
  create: (data: Record<string, unknown>) => apiClient.post('/api/v1/servers', data),
  update: (id: string, data: Record<string, unknown>) => apiClient.put(`/api/v1/servers/${id}`, data),
  delete: (id: string) => apiClient.delete(`/api/v1/servers/${id}`),
  test: (id: string) => apiClient.post(`/api/v1/servers/${id}/test`),
}

// Users API
export const usersApi = {
  list: () => apiClient.get('/api/v1/users'),
  create: (data: Record<string, unknown>) => apiClient.post('/api/v1/users', data),
  update: (id: number, data: Record<string, unknown>) => apiClient.put(`/api/v1/users/${id}`, data),
  delete: (id: number) => apiClient.delete(`/api/v1/users/${id}`),
}

// Config Diff API
export const configDiffApi = {
  getDiff: (serverId: string, table?: string) =>
    apiClient.get(`/api/v1/config-diff/${serverId}`, { params: table ? { table } : {} }),
}

// Settings API
export const settingsApi = {
  getSystemInfo: () => apiClient.get('/api/v1/settings/info'),
  getAuditLogs: (params?: Record<string, unknown>) =>
    apiClient.get('/api/v1/settings/audit-logs', { params }),
  clearAuditLogs: (before?: string) =>
    apiClient.delete('/api/v1/settings/audit-logs', { params: before ? { before } : {} }),
}

// Clusters API
export const clustersApi = {
  list: () => apiClient.get('/api/v1/clusters'),
  create: (data: Record<string, unknown>) => apiClient.post('/api/v1/clusters', data),
  get: (id: string) => apiClient.get(`/api/v1/clusters/${id}`),
  update: (id: string, data: Record<string, unknown>) => apiClient.put(`/api/v1/clusters/${id}`, data),
  delete: (id: string) => apiClient.delete(`/api/v1/clusters/${id}`),
  listMembers: (id: string) => apiClient.get(`/api/v1/clusters/${id}/members`),
  addMember: (clusterId: string, data: Record<string, unknown>) =>
    apiClient.post(`/api/v1/clusters/${clusterId}/members`, data),
  removeMember: (clusterId: string, serverId: string) =>
    apiClient.delete(`/api/v1/clusters/${clusterId}/members/${serverId}`),
  getStatus: (id: string) => apiClient.get(`/api/v1/clusters/${id}/status`),
  sync: (id: string, data: Record<string, unknown>) =>
    apiClient.post(`/api/v1/clusters/${id}/sync`, data),
  configureVariables: (id: string, variables: Record<string, string>) =>
    apiClient.post(`/api/v1/clusters/${id}/configure-variables`, variables),
  discover: (id: string) => apiClient.get(`/api/v1/clusters/${id}/discover`),
  getSyncLogs: (id: string, limit?: number) =>
    apiClient.get(`/api/v1/clusters/${id}/sync-logs`, { params: { limit: limit || 50 } }),
}
