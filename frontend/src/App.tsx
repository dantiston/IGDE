import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { FeedProvider } from './feed/FeedContext'
import { FeedPage } from './feed/FeedPage'
import { GrammarsPage } from './pages/GrammarsPage'
import { SettingsPage } from './pages/SettingsPage'
import { AppProvider, useApp } from './state'
import type { Page } from './state'

const icon = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {d}
  </svg>
)

const NAV: { page: Page; label: string; icon: ReactNode }[] = [
  {
    page: 'workbench',
    label: 'Workbench',
    // a parse tree
    icon: icon(
      <>
        <circle cx="12" cy="5" r="2" />
        <circle cx="6" cy="18" r="2" />
        <circle cx="18" cy="18" r="2" />
        <path d="M12 7v4M12 11l-5 5M12 11l5 5" />
      </>,
    ),
  },
  {
    page: 'grammars',
    label: 'Grammars',
    icon: icon(<path d="M4 19.5V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2.5zM4 19.5A2 2 0 0 0 6 21h13M8 7h7M8 11h5" />),
  },
  {
    page: 'settings',
    label: 'ACE Settings',
    icon: icon(
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" />
      </>,
    ),
  },
]

const SIDEBAR_KEY = 'igde.sidebar.collapsed'

/** IDE-style navigation: collapses to an icon strip (Ctrl/⌘+B). */
function Sidebar() {
  const { page, navigate } = useApp()
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === '1'
    } catch {
      return false
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0')
    } catch {
      /* storage unavailable */
    }
  }, [collapsed])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        setCollapsed((c) => !c)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return (
    <nav className={`sidebar${collapsed ? ' collapsed' : ''}`} aria-label="Main">
      {NAV.map((n) => (
        <a
          key={n.page}
          href={`#/${n.page}`}
          className={page === n.page ? 'on' : ''}
          aria-current={page === n.page ? 'page' : undefined}
          aria-label={n.label}
          title={collapsed ? n.label : undefined}
          onClick={(e) => {
            e.preventDefault()
            navigate(n.page)
          }}
        >
          <span className="side-icon">{n.icon}</span>
          {!collapsed && <span className="side-label">{n.label}</span>}
        </a>
      ))}
      <span className="grow" />
      <button
        type="button"
        className="side-toggle ghost"
        onClick={() => setCollapsed(!collapsed)}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-expanded={!collapsed}
        title={`${collapsed ? 'Expand' : 'Collapse'} sidebar (Ctrl+B)`}
      >
        {collapsed ? '»' : '«'}
        {!collapsed && <span className="side-label">Collapse</span>}
      </button>
    </nav>
  )
}

function Header() {
  const { status, statusError, setActiveGrammar, navigate, notify } = useApp()
  const ace = status?.ace
  return (
    <header className="app-header">
      <div className="brand">
        <img src="/favicon.svg" alt="" width={24} height={24} />
        <span>IGDE</span>
        <small>Integrated Grammar Development Environment</small>
      </div>
      <div className="header-right">
        {status && status.grammars.length > 0 && (
          <label className="grammar-select">
            <span>Grammar</span>
            <select
              aria-label="Active grammar"
              value={status.settings.activeGrammar ?? ''}
              onChange={async (e) => {
                try {
                  await setActiveGrammar(Number(e.target.value))
                } catch (err) {
                  notify((err as Error).message, 'error')
                }
              }}
            >
              {status.grammars.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          className={`ace-pill ${statusError ? 'bad' : ace?.ok ? 'ok' : 'bad'}`}
          onClick={() => navigate('settings')}
          title={statusError ?? ace?.executable ?? ace?.error ?? ''}
        >
          {statusError ? 'server offline' : ace?.ok ? `ACE ${ace.version}` : 'ACE not configured'}
        </button>
      </div>
    </header>
  )
}

function Toasts() {
  const { toasts, dismiss } = useApp()
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
          <span>{t.text}</span>
          <button type="button" className="ghost" onClick={() => dismiss(t.id)} aria-label="Dismiss">
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

function Shell() {
  const { page, statusError, status } = useApp()
  return (
    <div className="app">
      <Header />
      <div className="app-body">
        <Sidebar />
        <main className="app-main">
          {statusError && !status ? (
            <div className="page">
              <div className="error">{statusError}</div>
            </div>
          ) : (
            <>
              {page === 'workbench' && <FeedPage />}
              {page === 'grammars' && <GrammarsPage />}
              {page === 'settings' && <SettingsPage />}
            </>
          )}
        </main>
      </div>
      <Toasts />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <FeedProvider>
        <Shell />
      </FeedProvider>
    </AppProvider>
  )
}
