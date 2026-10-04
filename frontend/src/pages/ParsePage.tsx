import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import { api } from '../api'
import { SemanticsPanel } from '../components/MrsView'
import { TreeView, fromDerivation, fromLabelled } from '../components/Tree'
import { useAction, useApp } from '../state'
import type { Intent } from '../state'
import type { ParseResponse } from '../types'
import { GrammarRequired, ResponseMessages, useHistory } from './common'

export function ParsePage() {
  const { status, navigate, takeIntent } = useApp()
  const [sentence, setSentence] = useState('')
  const [n, setN] = useState('')
  const [resp, setResp] = useState<ParseResponse | null>(null)
  const [selected, setSelected] = useState(0)
  const [treeMode, setTreeMode] = useState<'labels' | 'derivation'>('labels')
  const history = useHistory('igde.parse.history')
  const parse = useAction(api.parse)
  const grammar = status?.activeGrammar

  const run = async (s: string) => {
    if (!s.trim()) return
    history.add(s.trim())
    const r = await parse.run(s.trim(), grammar?.id, n ? Number(n) : undefined)
    if (r) {
      setResp(r)
      setSelected(0)
    }
  }

  const onIntent = useEffectEvent((i: Extract<Intent, { page: 'parse' }>) => {
    setSentence(i.sentence)
    void run(i.sentence)
  })
  useEffect(() => {
    const i = takeIntent('parse')
    if (i) onIntent(i)
  }, [takeIntent])

  const result = resp?.results[selected]
  const tree = useMemo(() => {
    if (!result) return null
    if (treeMode === 'labels' && result.tree) return fromLabelled(result.tree)
    return result.derivation ? fromDerivation(result.derivation) : null
  }, [result, treeMode])

  if (status && !grammar) return <GrammarRequired />

  return (
    <div className="page">
      <form
        className="input-bar"
        onSubmit={(e) => {
          e.preventDefault()
          void run(sentence)
        }}
      >
        <input
          className="sentence"
          value={sentence}
          onChange={(e) => setSentence(e.target.value)}
          placeholder="Type a sentence to parse…"
          aria-label="Sentence"
          list="parse-history"
          autoFocus
        />
        <datalist id="parse-history">
          {history.items.map((h) => (
            <option key={h} value={h} />
          ))}
        </datalist>
        <input
          className="n-input"
          type="number"
          min={1}
          value={n}
          onChange={(e) => setN(e.target.value)}
          placeholder={String(status?.settings.maxResults ?? 5)}
          aria-label="Maximum results"
          title="Maximum number of results (ACE -n)"
        />
        <button type="submit" className="primary" disabled={parse.busy || !sentence.trim()}>
          {parse.busy ? 'Parsing…' : 'Parse'}
        </button>
      </form>
      {parse.error && <div className="error">{parse.error}</div>}
      {resp && (
        <>
          <div className="summary" data-testid="parse-summary">
            <strong>{resp.readings ?? resp.results.length}</strong> reading{resp.readings === 1 ? '' : 's'} for “{resp.input}”
            {resp.results.length < (resp.readings ?? 0) && <span className="muted"> (showing {resp.results.length})</span>}
            {resp.time !== null && <span className="muted"> · {resp.time} ms</span>}
          </div>
          <ResponseMessages r={resp} />
          {resp.results.length > 0 && (
            <div className="results">
              <div className="result-tabs" role="tablist" aria-label="Parse results">
                {resp.results.map((r, i) => (
                  <button
                    key={i}
                    type="button"
                    role="tab"
                    aria-selected={selected === i}
                    className={selected === i ? 'on' : ''}
                    onClick={() => setSelected(i)}
                  >
                    #{i + 1}
                    {r.probability !== null && <span className="prob">{(r.probability * 100).toFixed(1)}%</span>}
                  </button>
                ))}
              </div>
              {result && (
                <div className="result card">
                  <div className="row wrap">
                    <div className="segmented">
                      <button type="button" className={treeMode === 'labels' ? 'on' : ''} onClick={() => setTreeMode('labels')} disabled={!result.tree}>
                        Labelled tree
                      </button>
                      <button type="button" className={treeMode === 'derivation' ? 'on' : ''} onClick={() => setTreeMode('derivation')}>
                        Derivation
                      </button>
                    </div>
                    <span className="grow" />
                    <button
                      type="button"
                      onClick={() => navigate('tfs', { page: 'tfs', sentence: resp.input ?? sentence, signature: result.signature })}
                    >
                      Inspect feature structures
                    </button>
                    <button
                      type="button"
                      disabled={!result.mrsString}
                      onClick={() => navigate('generate', { page: 'generate', mrs: result.simplemrs ?? result.mrsString ?? '' })}
                    >
                      Generate from this MRS
                    </button>
                  </div>
                  {tree && <TreeView root={tree} ariaLabel={`Parse tree ${selected + 1}`} />}
                  <SemanticsPanel
                    key={selected}
                    mrs={result.mrs}
                    simplemrs={result.simplemrs}
                    dmrs={result.dmrs}
                    simpledmrs={result.simpledmrs}
                    eds={result.eds}
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
