import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '../api/client'
import { useI18n } from '../i18n'
import { Users, Plus, Trash2 } from 'lucide-react'

export default function UsersPage() {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const [showCreate, setShowCreate] = useState(false)
  const [newUser, setNewUser] = useState({
    username: '', password: '', confirmPassword: '', role: 'viewer',
  })
  const [passwordError, setPasswordError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => usersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowCreate(false)
      setNewUser({ username: '', password: '', confirmPassword: '', role: 'viewer' })
      setPasswordError('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => usersApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const users = data?.data || []

  const handleCreate = () => {
    if (newUser.password !== newUser.confirmPassword) {
      setPasswordError(t('users.passwordMismatch'))
      return
    }
    setPasswordError('')
    createMutation.mutate({
      username: newUser.username,
      password: newUser.password,
      role: newUser.role,
    })
  }

  const roleLabel = (role: string) => {
    if (role === 'admin') return t('users.role.admin')
    if (role === 'operator') return t('users.role.operator')
    return t('users.role.viewer')
  }

  const inputCls = 'px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users size={28} className="text-blue-600 dark:text-blue-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('users.title')}</h2>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus size={16} />
          {t('users.add')}
        </button>
      </div>

      {/* Create User Form */}
      {showCreate && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-6">
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('users.add')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <input
              type="text"
              placeholder={t('users.username')}
              value={newUser.username}
              onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
              className={inputCls}
            />
            <input
              type="password"
              placeholder={t('users.password')}
              value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
              className={inputCls}
            />
            <input
              type="password"
              placeholder={t('users.confirmPassword')}
              value={newUser.confirmPassword}
              onChange={(e) => setNewUser({ ...newUser, confirmPassword: e.target.value })}
              className={`px-3 py-2 border rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100 ${
                passwordError ? 'border-red-400 dark:border-red-500' : 'border-gray-300 dark:border-slate-600'
              }`}
            />
            <select
              value={newUser.role}
              onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
              className={inputCls}
            >
              <option value="viewer">{t('users.role.viewer')}</option>
              <option value="operator">{t('users.role.operator')}</option>
              <option value="admin">{t('users.role.admin')}</option>
            </select>
          </div>
          {passwordError && (
            <p className="text-xs text-red-600 dark:text-red-400 mb-3">{passwordError}</p>
          )}
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={!newUser.username || !newUser.password || createMutation.isPending}
              className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {t('common.add')}
            </button>
            <button
              onClick={() => {
                setShowCreate(false)
                setPasswordError('')
              }}
              className="text-gray-600 dark:text-slate-400 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Users Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('users.username')}</th>
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('users.email')}</th>
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('users.role')}</th>
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('common.status')}</th>
                <th className="text-right py-2 px-4 text-gray-600 dark:text-slate-400">{t('users.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user: any) => (
                <tr key={user.id} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="py-2 px-4 font-medium text-gray-900 dark:text-slate-100">{user.username}</td>
                  <td className="py-2 px-4 text-gray-500 dark:text-slate-400">{user.email || '-'}</td>
                  <td className="py-2 px-4">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                      user.role === 'admin' ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400' :
                      user.role === 'operator' ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400' :
                      'bg-gray-100 dark:bg-slate-600 text-gray-700 dark:text-slate-300'
                    }`}>
                      {roleLabel(user.role)}
                    </span>
                  </td>
                  <td className="py-2 px-4">
                    <span className={`text-xs ${user.is_active ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {user.is_active ? t('common.yes') : t('common.no')}
                    </span>
                  </td>
                  <td className="py-2 px-4 text-right">
                    <button
                      onClick={() => deleteMutation.mutate(user.id)}
                      className="text-red-500 hover:text-red-700 p-1"
                      title={t('common.delete')}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
