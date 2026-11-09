import {
  ApiOutlined,
  BarChartOutlined,
  DashboardOutlined,
  DownOutlined,
  LogoutOutlined,
  MenuOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { authApi } from '../api/client'
import { pageTitleForPath, ROLE_LABEL, initials } from '../lib/format'
import { useAuthStore } from '../store/auth'

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? 'brand-compact' : ''}`.trim()}>
      <span className="brand-mark" aria-hidden="true">
        MR
      </span>
      {compact ? null : (
        <span className="brand-copy">
          <strong>MedRisk</strong>
          <small>专科疾病风险分级</small>
        </span>
      )}
    </div>
  )
}

function navClass(active: boolean): string {
  return `side-nav-link${active ? ' is-active' : ''}`
}

export function AppShell() {
  const user = useAuthStore((state) => state.user)
  const clear = useAuthStore((state) => state.clear)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [menuOpen, setMenuOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await authApi.logout()
    } catch {
      // The local session is cleared even if the network call fails.
    } finally {
      clear()
      queryClient.clear()
      setLoggingOut(false)
      navigate('/login', { replace: true })
    }
  }

  const accountItems: MenuProps['items'] = [
    {
      key: 'account',
      label: (
        <div className="account-menu-meta">
          <strong>{user?.display_name ?? '未登录'}</strong>
          <span>
            {user ? ROLE_LABEL[user.role] : '—'} · {user?.username ?? '—'}
          </span>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => void handleLogout(),
    },
  ]

  const isPatientArea =
    location.pathname.startsWith('/patients') || location.pathname.startsWith('/assessments')
  const isAdmin = user?.role === 'ADMIN'

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>

      {menuOpen ? (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label="关闭导航"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <aside className={`app-sidebar${menuOpen ? ' is-open' : ''}`}>
        <div className="sidebar-brand-wrap">
          <Brand />
        </div>

        <nav className="side-nav" aria-label="主导航">
          <div className="side-nav-group">
            <span className="side-nav-label">临床工作</span>
            <NavLink to="/" end className={({ isActive }) => navClass(isActive)}>
              <DashboardOutlined />
              <span>工作台</span>
            </NavLink>
            <NavLink to="/patients" className={() => navClass(isPatientArea)}>
              <TeamOutlined />
              <span>患者管理</span>
            </NavLink>
            <NavLink to="/analytics" className={({ isActive }) => navClass(isActive)}>
              <BarChartOutlined />
              <span>数据分析</span>
            </NavLink>
          </div>

          <div className="side-nav-group">
            <span className="side-nav-label">系统</span>
            <NavLink to="/models" className={({ isActive }) => navClass(isActive)}>
              <ApiOutlined />
              <span>模型与规则</span>
            </NavLink>
            {isAdmin ? (
              <NavLink to="/settings" className={({ isActive }) => navClass(isActive)}>
                <SettingOutlined />
                <span>系统设置</span>
              </NavLink>
            ) : null}
          </div>
        </nav>

        <div className="sidebar-foot">
          <div className="demo-notice">
            <span className="demo-notice-dot" aria-hidden="true" />
            <div>
              <strong>演示环境</strong>
              <span>仅使用虚构患者数据</span>
            </div>
          </div>
          <p>概率未经校准，不替代医生决策。</p>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-menu-button"
              aria-label="打开导航"
              onClick={() => setMenuOpen(true)}
            >
              <MenuOutlined />
            </button>
            <span className="topbar-title">{pageTitleForPath(location.pathname)}</span>
            <span className="topbar-divider" aria-hidden="true" />
            <span className="topbar-context">临床风险分级</span>
          </div>

          <div className="topbar-right">
            <span className="env-chip">DEMO</span>
            <span className="topbar-divider" aria-hidden="true" />
            <Dropdown
              menu={{ items: accountItems }}
              trigger={['click']}
              placement="bottomRight"
              disabled={loggingOut}
            >
              <button type="button" className="account-trigger" aria-label="账号菜单">
                <span className="account-avatar" aria-hidden="true">
                  {user ? initials(user.display_name) : <UserOutlined />}
                </span>
                <span className="account-copy">
                  <strong>{user?.display_name ?? '—'}</strong>
                  <small>{user ? ROLE_LABEL[user.role] : '—'}</small>
                </span>
                <DownOutlined className="account-caret" />
              </button>
            </Dropdown>
          </div>
        </header>

        <main id="main-content" className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function AuthSplash() {
  return (
    <div className="app-splash" role="status">
      <div className="app-splash-card">
        <Brand />
        <span className="splash-spinner" aria-hidden="true" />
        <p>正在验证安全会话</p>
      </div>
    </div>
  )
}

