import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import { api } from '../api'
import { TreeView, fromDerivation, fromLabelled } from '../components/Tree'
import { useAction, useApp } from '../state'
import type { Intent } from '../state'
import type { GenerateResponse } from '../types'
import { GrammarRequired, ResponseMessages } from './common'

const DRAFT_KEY = 'igde.generate.mrs'

export function GeneratePage() {
  const { status, takeIntent, navigate } = useApp()
  const [mrs, setMrs] = useState(() => {
    try {
      return localStorage.getItem(DRAFT_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [n, setN] = useState('')
  const [resp, setResp] = useState<GenerateResponse | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const gen = useAction(api.generate)
  const grammar = status?.activeGrammar

  const run = async (text: string) => {
    if (!text.trim()) return
    const r = await gen.run(text, grammar?.id, n ? Number(n) : undefined)
    if (r) {
      setResp(r)
      setSelected(r.results.length ? 0 : null)
    }
  }

  const onIntent = useEffectEvent((i: Extract<Intent, { page: 'generate' }>) => {
    setMrs(i.mrs)
    void run(i.mrs)
  })
  useEffect(() => {
    const i = takeIntent('generate')
    if (i) onIntent(i)
  }, [takeIntent])

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, mrs)
    } catch {
      /* ignore */
    }
  }, [mrs])

  const result = selected !== null ? resp?.results[selected] : undefined
  const tree = useMemo(() => {
    if (!result) return null
    if (result.tree) return fromLabelled(result.tree)
    return result.derivation ? fromDerivation(result.derivation) : null
  }, [result])

  if (status && !grammar) return <GrammarRequired />

  return (
    <div className="page">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault()
          void run(mrs)
        }}
      >
        <label className="field">
          <span>Input MRS (SimpleMRS)</span>
          <textarea
            className="mrs-input"
            value={mrs}
            onChange={(e) => setMrs(e.target.value)}
            placeholder="[ LTOP: h0 INDEX: e2 RELS: < … > HCONS: < … > ]  (tip: parse a sentence and click “Generate from this MRS”)"
            aria-label="Input MRS"
            spellCheck={false}
            rows={8}
          />
        </label>
        <div className="row end">
          <input
            className="n-input"
            type="number"
            min={1}
            value={n}
            onChange={(e) => setN(e.target.value)}
            placeholder={String(status?.settings.maxResults ?? 5)}
            aria-label="Maximum results"
            title="Maximum number of realizations (ACE -n)"
          />
          <button type="submit" className="primary" disabled={gen.busy || !mrs.trim()}>
            {gen.busy ? 'Generating…' : 'Generate'}
          </button>
        </div>
      </form>
      {gen.error && <div className="error">{gen.error}</div>}
      {resp && (
        <>
          <div className="summary" data-testid="generate-summary">
            <strong>{resp.results.length}</strong> realization{resp.results.length === 1 ? '' : 's'}
            {resp.time !== null && <span className="muted"> · {resp.time} ms</span>}
          </div>
          <ResponseMessages r={resp} />
          <ol className="realizations">
            {resp.results.map((r, i) => (
              <li key={i} className={selected === i ? 'on' : ''}>
                <button type="button" className="realization" onClick={() => setSelected(i)}>
                  {r.surface}
                </button>
                {r.probability !== null && <span className="prob">{(r.probability * 100).toFixed(1)}%</span>}
                <button type="button" className="small ghost" onClick={() => navigate('parse', { page: 'parse', sentence: r.surface })}>
                  Parse
                </button>
              </li>
            ))}
          </ol>
          {tree && (
            <div className="card">
              <TreeView root={tree} ariaLabel="Realization tree" />
            </div>
          )}
        </>
      )}
    </div>
  )
}
