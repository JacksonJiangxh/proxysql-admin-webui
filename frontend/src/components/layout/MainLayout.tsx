import { useState, useMemo, useCallback } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { useI18n } from '../../i18n'
import ServerSelector from '../ServerSelector'
import LanguageSwitcher from '../LanguageSwitcher'
import ThemeToggle from '../ThemeToggle'
import {
  LayoutDashboard, Wand2, Table, Terminal, RefreshCw,
  Users, Server, LogOut, Menu, X, GitCompare, Settings,
  Network, Rocket,
} from 'lucide-react'

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { user, logout } = useAuthStore()
  const { t } = useI18n()
  const navigate = useNavigate()

  // useMemo: navigation items list is stable and only depends on t (i18n).
  // Without memoization, a new array would be created on every render,
  // causing NavLink children to re-render unnecessarily.
  const navItems = useMemo(() => [
    { path: '/dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { path: '/wizards', label: t('nav.wizards'), icon: Wand2 },
    { path: '/template', label: t('nav.template'), icon: Rocket },
    { path: '/tables', label: t('nav.tables'), icon: Table },
    { path: '/query', label: t('nav.query'), icon: Terminal },
    { path: '/sync', label: t('nav.sync'), icon: RefreshCw },
    { path: '/config-diff', label: t('nav.configDiff'), icon: GitCompare },
    { path: '/servers', label: t('nav.servers'), icon: Server },
    { path: '/clusters', label: t('nav.clusters'), icon: Network },
    { path: '/users', label: t('nav.users'), icon: Users },
    { path: '/settings', label: t('nav.settings'), icon: Settings },
  ], [t])

  // useCallback: stable handler across renders
  const handleLogout = useCallback(() => {
    logout()
    navigate('/login')
  }, [logout, navigate])

  const handleToggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev)
  }, [])

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-slate-900">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-16'} bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700 flex flex-col transition-all duration-200`}>
        <div className="h-14 flex items-center justify-between px-4 border-b border-gray-200 dark:border-slate-700">
          {sidebarOpen && <h1 className="text-lg font-bold text-blue-600 dark:text-blue-400">{t('login.title')}</h1>}
          <button
            onClick={handleToggleSidebar}
            className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded"
          >
            {sidebarOpen ? <X size={18} className="text-gray-600 dark:text-slate-400" /> : <Menu size={18} className="text-gray-600 dark:text-slate-400" />}
          </button>
        </div>

        <nav className="flex-1 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center px-4 py-2.5 mx-2 rounded-lg mb-0.5 transition-colors ${
                  isActive
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                }`
              }
            >
              <item.icon size={20} />
              {sidebarOpen && <span className="ml-3 text-sm font-medium">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-200 dark:border-slate-700">
          {sidebarOpen && (
            <div className="mb-3">
              <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{user?.username}</p>
              <p className="text-xs text-gray-500 dark:text-slate-400 capitalize">{user?.role}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center text-sm text-gray-600 dark:text-slate-400 hover:text-red-600 w-full"
          >
            <LogOut size={18} />
            {sidebarOpen && <span className="ml-2">{t('layout.logout')}</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {/* Top bar with server selector and language switcher */}
        <div className="h-14 flex items-center justify-between px-6 border-b border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800">
          <ServerSelector />
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <ThemeToggle />
            <div className="text-sm text-gray-500 dark:text-slate-400">
              {user?.username} <span>({t(`layout.role.${user?.role}`) !== `layout.role.${user?.role}` ? t(`layout.role.${user?.role}`) : user?.role})</span>
            </div>
          </div>
        </div>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
