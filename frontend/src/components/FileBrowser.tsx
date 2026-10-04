import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { FsEntry, FsListing } from '../types'

const HINT_LABEL: Record<string, string> = {
  'grammar-dir': 'grammar',
  config: 'grammar config',
  image: 'grammar image',
}

const LAST_PATH_KEY = 'igde.fileBrowser.lastPath'

function formatSize(n: number | null) {
  if (n === null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export interface FileBrowserProps {
  /** Start here (otherwise the last visited directory, or home). */
  initialPath?: string
  /** 'pick-dir' shows a "Choose this folder" button; 'pick-file' lets files be picked. */
  mode?: 'browse' | 'pick-dir' | 'pick-file'
  /** Which files may be picked in 'pick-file' mode. */
  accept?: (e: FsEntry) => boolean
  onPick?: (path: string, entry?: FsEntry) => void
  onOpenFile?: (e: FsEntry) => void
  /** Extra per-entry buttons (e.g. "Add as grammar"). */
  entryActions?: (e: FsEntry) => ReactNode
  /** Extra buttons for the current directory. */
  dirActions?: (listing: FsListing) => ReactNode
  selectedPath?: string | null
}

export function FileBrowser({
  initialPath,
  mode = 'browse',
  accept,
  onPick,
  onOpenFile,
  entryActions,
  dirActions,
  selectedPath,
}: FileBrowserProps) {
  const [listing, setListing] = useState<FsListing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hidden, setHidden] = useState(false)
  const [typed, setTyped] = useState('')
  const [roots, setRoots] = useState<{ name: string; path: string }[]>([])
  const current = useRef<string | null>(null)
  const startedAt = useRef<string | undefined>(undefined)

  const seq = useRef(0)
  const typedRef = useRef('')
  const editType = (v: string) => {
    typedRef.current = v
    setTyped(v)
  }

  const load = useCallback(
    async (path?: string) => {
      const mine = ++seq.current
      const typedBefore = typedRef.current
      try {
        const l = await api.fsList(path, hidden)
        if (mine !== seq.current) return // a newer request superseded this one
        setListing(l)
        // don't clobber a path the user typed while this was loading
        if (typedRef.current === typedBefore || typedRef.current === path) {
          typedRef.current = l.path
          setTyped(l.path)
        }
        current.current = l.path
        setError(null)
        try {
          localStorage.setItem(LAST_PATH_KEY, l.path)
        } catch {
          /* storage unavailable */
        }
      } catch (e) {
        if (mine === seq.current) setError((e as Error).message)
      }
    },
    [hidden],
  )

  useEffect(() => {
    // Stay in the current directory when only `hidden` changed.
    let start = startedAt.current === initialPath && current.current ? current.current : initialPath
    startedAt.current = initialPath
    if (!start) {
      try {
        start = localStorage.getItem(LAST_PATH_KEY) ?? undefined
      } catch {
        start = undefined
      }
    }
    void load(start)
    // `load` changes with `hidden`: reload, staying in the same directory
  }, [initialPath, load])

  useEffect(() => {
    api.fsRoots().then((r) => setRoots(r.roots), () => {})
  }, [])

  const crumbs = listing
    ? listing.path
        .split('/')
        .filter(Boolean)
        .map((part, i, all) => ({ name: part, path: '/' + all.slice(0, i + 1).join('/') }))
    : []

  const pickable = (e: FsEntry) => mode === 'pick-file' && e.kind === 'file' && (!accept || accept(e))

  return (
    <div className="file-browser">
      <div className="fb-toolbar">
        <select
          aria-label="Quick locations"
          value=""
          onChange={(e) => e.target.value && void load(e.target.value)}
        >
          <option value="">Go to…</option>
          {roots.map((r) => (
            <option key={r.path} value={r.path}>
              {r.name} ({r.path})
            </option>
          ))}
        </select>
        <form
          className="fb-path"
          onSubmit={(e) => {
            e.preventDefault()
            void load(typed)
          }}
        >
          <input aria-label="Path" value={typed} onChange={(e) => editType(e.target.value)} spellCheck={false} />
          <button type="submit">Go</button>
        </form>
        <label className="fb-hidden">
          <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} /> hidden
        </label>
      </div>
      <nav className="fb-crumbs" aria-label="Current folder">
        <button type="button" className="link" onClick={() => void load('/')}>
          /
        </button>
        {crumbs.map((c, i) => (
          <span key={c.path}>
            {i > 0 && <span className="sep">/</span>}
            <button type="button" className="link" onClick={() => void load(c.path)}>
              {c.name}
            </button>
          </span>
        ))}
        {listing?.hint && <span className="badge hint">{HINT_LABEL[listing.hint] ?? listing.hint}</span>}
      </nav>
      {(mode === 'pick-dir' || dirActions) && listing && (
        <div className="fb-diractions">
          {mode === 'pick-dir' && onPick && (
            <button type="button" className="primary" onClick={() => onPick(listing.path)}>
              Choose this folder
            </button>
          )}
          {dirActions?.(listing)}
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <ul className="fb-list" role="list">
        {listing?.parent && (
          <li>
            <button type="button" className="fb-entry dir" onClick={() => void load(listing.parent!)}>
              <span className="fb-icon">↰</span> ..
            </button>
          </li>
        )}
        {listing?.entries.map((e) => (
          <li key={e.path} className={selectedPath === e.path ? 'selected' : ''}>
            <button
              type="button"
              className={`fb-entry ${e.kind}${pickable(e) ? ' pickable' : ''}`}
              onClick={() => {
                if (e.kind === 'dir') void load(e.path)
                else if (pickable(e)) onPick?.(e.path, e)
                else onOpenFile?.(e)
              }}
              title={e.path}
            >
              <span className="fb-icon">{e.kind === 'dir' ? '📁' : e.hint === 'image' ? '⚙' : '📄'}</span>
              <span className="fb-name">{e.name}</span>
              {e.hint && HINT_LABEL[e.hint] && <span className={`badge hint-${e.hint}`}>{HINT_LABEL[e.hint]}</span>}
              <span className="fb-size">{formatSize(e.size)}</span>
            </button>
            {entryActions && <span className="fb-actions">{entryActions(e)}</span>}
          </li>
        ))}
        {listing && !listing.entries.length && <li className="muted">(empty)</li>}
      </ul>
    </div>
  )
}
