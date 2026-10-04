import { useCallback, useState } from 'react'
import { useApp } from '../state'

export function GrammarRequired() {
  const { status, navigate } = useApp()
  return (
    <div className="page">
      <div className="empty">
        {status?.ace.ok ? (
          <>
            No grammar selected.{' '}
            <button type="button" className="primary" onClick={() => navigate('grammars')}>
              Add a grammar
            </button>
          </>
        ) : (
          <>
            ACE is not configured yet.{' '}
            <button type="button" className="primary" onClick={() => navigate('settings')}>
              Configure ACE
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export function ResponseMessages({ r }: { r: { error: string | null; warnings: string[]; errors: string[] } }) {
  if (!r.error && !r.warnings.length && !r.errors.length) return null
  return (
    <div className="messages">
      {r.error && <div className="error">ACE: {r.error}</div>}
      {r.errors.map((m, i) => (
        <div key={`e${i}`} className="error">
          {m}
        </div>
      ))}
      {r.warnings.map((m, i) => (
        <div key={`w${i}`} className="warning">
          {m}
        </div>
      ))}
    </div>
  )
}

/** A small most-recent-first history persisted in localStorage. */
export function useHistory(key: string, max = 30) {
  const [items, setItems] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? '[]') as string[]
    } catch {
      return []
    }
  })
  const add = useCallback(
    (item: string) => {
      setItems((prev) => {
        const next = [item, ...prev.filter((x) => x !== item)].slice(0, max)
        try {
          localStorage.setItem(key, JSON.stringify(next))
        } catch {
          /* ignore */
        }
        return next
      })
    },
    [key, max],
  )
  return { items, add }
}
