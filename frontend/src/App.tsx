import { api } from './api'
import { FilesPage } from './pages/FilesPage'
import { GeneratePage } from './pages/GeneratePage'
import { GrammarsPage } from './pages/GrammarsPage'
import { ParsePage } from './pages/ParsePage'
import { SettingsPage } from './pages/SettingsPage'
import { TfsPage } from './pages/TfsPage'
import { AppProvider, useApp } from './state'
import type { Page } from './state'

const NAV: { page: Page; label: string }[] = [
  { page: 'parse', label: 'Parse' },
  { page: 'generate', label: 'Generate' },
  { page: 'tfs', label: 'TFS Browser' },
  { page: 'grammars', label: 'Grammars' },
  { page: 'files', label: 'Files' },
  { page: 'settings', label: 'ACE Settings' },
]

function Header() {
  const { status, statusError, refresh, navigate, notify } = useApp()
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
                  await api.activateGrammar(Number(e.target.value))
                  await refresh()
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
  const { page, navigate, statusError, status } = useApp()
  return (
    <div className="app">
      <Header />
      <nav className="app-nav" aria-label="Main">
        {NAV.map((n) => (
          <a
            key={n.page}
            href={`#/${n.page}`}
            className={page === n.page ? 'on' : ''}
            aria-current={page === n.page ? 'page' : undefined}
            onClick={(e) => {
              e.preventDefault()
              navigate(n.page)
            }}
          >
            {n.label}
          </a>
        ))}
      </nav>
      <main className="app-main">
        {statusError && !status ? (
          <div className="page">
            <div className="error">{statusError}</div>
          </div>
        ) : (
          <>
            {page === 'parse' && <ParsePage />}
            {page === 'generate' && <GeneratePage />}
            {page === 'tfs' && <TfsPage />}
            {page === 'grammars' && <GrammarsPage />}
            {page === 'files' && <FilesPage />}
            {page === 'settings' && <SettingsPage />}
          </>
        )}
      </main>
      <Toasts />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  )
}
