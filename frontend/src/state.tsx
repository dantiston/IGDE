import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from './api'
import type { Status } from './types'

export const PAGES = ['parse', 'generate', 'tfs', 'grammars', 'files', 'settings'] as const
export type Page = (typeof PAGES)[number]

/** One-shot hand-offs between pages, e.g. "generate from this MRS". */
export type Intent =
  | { page: 'generate'; mrs: string }
  | { page: 'tfs'; sentence: string; signature?: string[] }
  | { page: 'files'; path: string; line?: number }
  | { page: 'parse'; sentence: string }

export interface Toast {
  id: number
  kind: 'info' | 'error' | 'success'
  text: string
}

interface AppState {
  status: Status | null
  statusError: string | null
  refresh: () => Promise<Status | null>
  page: Page
  navigate: (page: Page, intent?: Intent) => void
  takeIntent: <P extends Page>(page: P) => Extract<Intent, { page: P }> | null
  toasts: Toast[]
  notify: (text: string, kind?: Toast['kind']) => void
  dismiss: (id: number) => void
}

const Ctx = createContext<AppState | null>(null)

function pageFromHash(): Page {
  const h = window.location.hash.replace(/^#\/?/, '').split(/[?/]/)[0]
  return (PAGES as readonly string[]).includes(h) ? (h as Page) : 'parse'
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [page, setPage] = useState<Page>(pageFromHash)
  const [toasts, setToasts] = useState<Toast[]>([])
  const intent = useRef<Intent | null>(null)
  const toastId = useRef(0)

  const refresh = useCallback(async () => {
    try {
      const s = await api.status()
      setStatus(s)
      setStatusError(null)
      return s
    } catch (e) {
      setStatusError((e as Error).message)
      return null
    }
  }, [])

  useEffect(() => {
    void refresh()
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [refresh])

  const navigate = useCallback((p: Page, i?: Intent) => {
    intent.current = i ?? null
    if (pageFromHash() !== p) window.location.hash = `#/${p}`
    setPage(p)
  }, [])

  const takeIntent = useCallback(<P extends Page>(p: P) => {
    const i = intent.current
    if (i && i.page === p) {
      intent.current = null
      return i as Extract<Intent, { page: P }>
    }
    return null
  }, [])

  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const notify = useCallback(
    (text: string, kind: Toast['kind'] = 'info') => {
      const id = ++toastId.current
      setToasts((t) => [...t, { id, kind, text }])
      window.setTimeout(() => dismiss(id), kind === 'error' ? 8000 : 4000)
    },
    [dismiss],
  )

  const value = useMemo(
    () => ({ status, statusError, refresh, page, navigate, takeIntent, toasts, notify, dismiss }),
    [status, statusError, refresh, page, navigate, takeIntent, toasts, notify, dismiss],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp outside AppProvider')
  return v
}

/** Run an async action with loading/error state. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ref = useRef(fn)
  useLayoutEffect(() => {
    ref.current = fn
  })
  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    setBusy(true)
    setError(null)
    try {
      return await ref.current(...args)
    } catch (e) {
      setError((e as Error).message)
      return undefined
    } finally {
      setBusy(false)
    }
  }, [])
  return { run, busy, error, setError }
}
