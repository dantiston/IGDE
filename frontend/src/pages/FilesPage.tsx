import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { FileEditor } from '../components/FileEditor'
import { useApp } from '../state'

type Tab = 'grammar' | 'disk'

function dirname(p: string) {
  const i = p.lastIndexOf('/')
  return i > 0 ? p.slice(0, i) : '/'
}

export function FilesPage() {
  const { status, takeIntent, refresh, notify } = useApp()
  const [open, setOpen] = useState<{ path: string; line?: number } | null>(null)
  const [tab, setTab] = useState<Tab>('grammar')
  const [browseFrom, setBrowseFrom] = useState<string | undefined>(undefined)
  const [files, setFiles] = useState<{ path: string; rel: string; size: number }[] | null>(null)
  const [filesError, setFilesError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [needsRecompile, setNeedsRecompile] = useState(false)
  const grammar = status?.activeGrammar ?? null

  useEffect(() => {
    const intent = takeIntent('files')
    if (!intent) return
    // a directory (e.g. a grammar root) opens the browser; a file opens the editor
    if (/\.(tdl|rpp|vpm|mtr|tab|set|smi|txt|lsp)$/.test(intent.path) || intent.line) {
      setOpen({ path: intent.path, line: intent.line })
      setBrowseFrom(dirname(intent.path))
    } else {
      setBrowseFrom(intent.path)
      setTab('disk')
    }
  }, [takeIntent])

  useEffect(() => {
    if (!grammar) return
    setFiles(null)
    api.grammarFiles(grammar.id).then(
      (r) => {
        setFiles(r.files)
        setFilesError(null)
      },
      (e) => setFilesError((e as Error).message),
    )
  }, [grammar])

  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase()
    return (files ?? []).filter((x) => !f || x.rel.toLowerCase().includes(f))
  }, [files, filter])

  const onSaved = useCallback(
    (path: string) => {
      notify(`Saved ${path.split('/').pop()}`, 'success')
      if (grammar?.kind === 'source' && path.startsWith(grammar.rootDir)) setNeedsRecompile(true)
    },
    [grammar, notify],
  )

  return (
    <div className="page files-page">
      <aside className="files-side card">
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'grammar'} className={tab === 'grammar' ? 'on' : ''} onClick={() => setTab('grammar')}>
            Grammar files
          </button>
          <button type="button" role="tab" aria-selected={tab === 'disk'} className={tab === 'disk' ? 'on' : ''} onClick={() => setTab('disk')}>
            Browse disk
          </button>
        </div>
        {tab === 'grammar' &&
          (grammar ? (
            <>
              <div className="muted small">
                {grammar.name}: <code>{grammar.rootDir}</code>
              </div>
              <input placeholder="Filter files…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter files" />
              {filesError && <div className="error">{filesError}</div>}
              <ul className="fb-list" role="list">
                {shown.map((f) => (
                  <li key={f.path} className={open?.path === f.path ? 'selected' : ''}>
                    <button type="button" className="fb-entry file" onClick={() => setOpen({ path: f.path })} title={f.path}>
                      <span className="fb-icon">📄</span>
                      <span className="fb-name">{f.rel}</span>
                    </button>
                  </li>
                ))}
                {files && !shown.length && <li className="muted">No matching files.</li>}
              </ul>
            </>
          ) : (
            <div className="empty">No active grammar. Add one in the Grammars tab, or browse the disk.</div>
          ))}
        {tab === 'disk' && (
          <FileBrowser
            initialPath={browseFrom}
            selectedPath={open?.path}
            onOpenFile={(e) => setOpen({ path: e.path })}
          />
        )}
      </aside>
      <section className="files-main">
        {needsRecompile && grammar?.kind === 'source' && (
          <div className="banner">
            Grammar sources changed.{' '}
            <button
              type="button"
              className="primary"
              onClick={async () => {
                try {
                  await api.compileGrammar(grammar.id)
                  setNeedsRecompile(false)
                  notify(`Compiling ${grammar.name}… (see the Grammars tab)`)
                  await refresh()
                } catch (e) {
                  notify((e as Error).message, 'error')
                }
              }}
            >
              Recompile {grammar.name}
            </button>
          </div>
        )}
        {open ? (
          <FileEditor key={`${open.path}:${open.line ?? ''}`} path={open.path} line={open.line} onSaved={onSaved} />
        ) : (
          <div className="empty">Open a file to view or edit it.</div>
        )}
      </section>
    </div>
  )
}
