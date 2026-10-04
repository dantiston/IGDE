import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import { AvmView } from '../components/AvmView'
import { HierarchyView } from '../components/HierarchyView'
import { TreeView, fromLui } from '../components/Tree'
import { useAction, useApp } from '../state'
import type { Intent } from '../state'
import type { Avm, AvmDoc, HierarchyNode, LuiTree, TfsParse } from '../types'
import { GrammarRequired, useHistory } from './common'

type LookupKind = 'type' | 'lex' | 'rule' | 'instance'

interface Panel extends AvmDoc {
  key: number
  session: number
  source: string
  /** the root type, for "show in hierarchy" */
  rootType?: string
}

interface PathRef {
  panel: number
  path: string[]
}

const KIND_LABEL: Record<LookupKind, string> = {
  type: 'Type',
  lex: 'Lexical entry',
  rule: 'Rule',
  instance: 'Instance',
}

function findLuiNode(t: LuiTree, id: number): LuiTree | null {
  if (t.id === id) return t
  for (const c of t.children) {
    const f = findLuiNode(c, id)
    if (f) return f
  }
  return null
}

const rootTypeOf = (a: Avm) => ('type' in a ? a.type : undefined)

export function TfsPage() {
  const { status, takeIntent, navigate, notify } = useApp()
  const grammar = status?.activeGrammar ?? null
  const [sentence, setSentence] = useState('')
  const [parse, setParse] = useState<TfsParse | null>(null)
  const [treeIdx, setTreeIdx] = useState(0)
  const [showRules, setShowRules] = useState(false)
  const [selectedNode, setSelectedNode] = useState<number | null>(null)
  const [kind, setKind] = useState<LookupKind>('type')
  const [name, setName] = useState('')
  const [matches, setMatches] = useState<{ kind: LookupKind; names: string[]; more?: string | null } | null>(null)
  const [hier, setHier] = useState<{ name: string; nodes: HierarchyNode[] } | null>(null)
  const [panels, setPanels] = useState<Panel[]>([])
  const [source, setSource] = useState<PathRef | null>(null)
  const [target, setTarget] = useState<PathRef | null>(null)
  const nextKey = useRef(1)
  const history = useHistory('igde.tfs.history')

  const handleError = useCallback(
    (e: unknown) => {
      // ACE was restarted: old chart/AVM ids are gone (panels stay viewable).
      if (e instanceof ApiError && e.data.stale) setParse(null)
      notify((e as Error).message, 'error')
    },
    [notify],
  )

  const addPanel = useCallback((p: Omit<Panel, 'key'>) => {
    const key = nextKey.current++
    setPanels((ps) => [{ ...p, key }, ...ps].slice(0, 12))
    return key
  }, [])

  const parser = useAction(async (s: string, signature?: string[]) => {
    history.add(s)
    const r = await api.tfsParse(s, grammar?.id)
    setParse(r)
    setSelectedNode(null)
    let idx = 0
    if (signature) {
      const found = r.trees.findIndex((t) => t.signature?.join(' ') === signature.join(' '))
      if (found >= 0) idx = found
    }
    setTreeIdx(idx)
    return r
  })

  const onIntent = useEffectEvent((i: Extract<Intent, { page: 'tfs' }>) => {
    setSentence(i.sentence)
    void parser.run(i.sentence, i.signature)
  })
  useEffect(() => {
    const i = takeIntent('tfs')
    if (i) onIntent(i)
  }, [takeIntent])

  const showNode = async (id: number, what: 'avm' | 'mrs') => {
    if (!parse) return
    const node = parse.trees[treeIdx] ? findLuiNode(parse.trees[treeIdx], id) : null
    try {
      const r = await api.tfsNode(id, parse.session, grammar?.id, what)
      addPanel({
        ...r,
        session: r.session,
        source: what === 'mrs' ? `MRS of ${node?.entity ?? `#${id}`}` : `${node?.label ?? ''} ${node?.entity ?? ''} (edge ${node?.eid ?? id})`,
        rootType: rootTypeOf(r.avm),
      })
    } catch (e) {
      handleError(e)
    }
  }

  const lookup = async (k: LookupKind, n: string) => {
    if (!n.trim()) return
    try {
      const r = await api.tfsLookup(k, n.trim(), grammar?.id)
      if (r.avm && r.id !== undefined) {
        setMatches(null)
        addPanel({
          id: r.id,
          title: r.title ?? n,
          avm: r.avm,
          definition: r.definition,
          session: r.session,
          source: `${KIND_LABEL[k]} ${r.title ?? n}`,
          rootType: rootTypeOf(r.avm),
        })
      } else {
        setMatches({ kind: k, names: r.matches ?? [], more: r.more })
        if (!r.matches?.length) notify(r.message || `No ${KIND_LABEL[k].toLowerCase()} matching “${n}”`)
      }
    } catch (e) {
      handleError(e)
    }
  }

  const hierarchy = async (t: string) => {
    try {
      const r = await api.tfsHierarchy(t, grammar?.id)
      setHier({ name: t, nodes: r.nodes })
    } catch (e) {
      handleError(e)
    }
  }

  const pickPath = (panel: Panel, path: string[]) => {
    const ref = { panel: panel.key, path }
    if (!source || (target && source)) {
      setSource(ref)
      setTarget(null)
    } else {
      setTarget(ref)
    }
  }

  const unify = async () => {
    if (!source || !target) return
    const s = panels.find((p) => p.key === source.panel)
    const t = panels.find((p) => p.key === target.panel)
    if (!s || !t) return
    if (s.session !== t.session) {
      notify('These AVMs come from different TFS sessions; look them up again.', 'error')
      return
    }
    try {
      const r = await api.tfsUnify({ id: s.id, path: source.path }, { id: t.id, path: target.path }, s.session, grammar?.id)
      if (r.avm && r.id !== undefined) {
        addPanel({
          id: r.id,
          title: r.title ?? 'unification',
          avm: r.avm,
          failure: r.failure,
          session: r.session,
          source: `${r.ok ? 'Unification' : 'Failed unification'}: ${s.title} ${source.path.join('.') || '(root)'} ⊔ ${t.title} ${target.path.join('.') || '(root)'}`,
          rootType: rootTypeOf(r.avm),
        })
        notify(r.ok ? 'Unification succeeded' : `Unification failed at ${r.failure?.path.join('.') || '(root)'}`, r.ok ? 'success' : 'error')
      } else {
        notify(r.message ?? 'Unification failed', 'error')
      }
      setSource(null)
      setTarget(null)
    } catch (e) {
      handleError(e)
    }
  }

  const tree = parse?.trees[treeIdx]
  const tnode = useMemo(() => (tree ? fromLui(tree, showRules) : null), [tree, showRules])
  const selectedLui = tree && selectedNode !== null ? findLuiNode(tree, selectedNode) : null
  const panelTitle = (key: number) => panels.find((p) => p.key === key)?.title ?? '?'

  if (status && !grammar) return <GrammarRequired />

  return (
    <div className="page tfs-page">
      <div className="tfs-left">
        <section className="card">
          <h3>Parse chart</h3>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault()
              if (sentence.trim()) void parser.run(sentence.trim())
            }}
          >
            <input
              className="grow"
              value={sentence}
              onChange={(e) => setSentence(e.target.value)}
              placeholder="Sentence"
              aria-label="TFS sentence"
              list="tfs-history"
            />
            <datalist id="tfs-history">
              {history.items.map((h) => (
                <option key={h} value={h} />
              ))}
            </datalist>
            <button type="submit" className="primary" disabled={parser.busy}>
              {parser.busy ? 'Parsing…' : 'Parse'}
            </button>
          </form>
          {parser.error && <div className="error">{parser.error}</div>}
          {parse && (
            <>
              <div className="row wrap">
                <span className="muted" data-testid="tfs-summary">
                  {parse.count} tree{parse.count === 1 ? '' : 's'}
                </span>
                <div className="result-tabs">
                  {parse.trees.map((_, i) => (
                    <button key={i} type="button" className={i === treeIdx ? 'on' : ''} onClick={() => (setTreeIdx(i), setSelectedNode(null))}>
                      #{i + 1}
                    </button>
                  ))}
                </div>
                <label className="small">
                  <input type="checkbox" checked={showRules} onChange={(e) => setShowRules(e.target.checked)} /> rule names
                </label>
              </div>
              {tnode && (
                <>
                  <p className="muted small">Click a node to inspect its feature structure.</p>
                  <TreeView
                    root={tnode}
                    selected={selectedNode !== null ? String(selectedNode) : null}
                    onSelect={(n) => {
                      const id = Number(n.key)
                      setSelectedNode(id)
                      void showNode(id, 'avm')
                    }}
                    ariaLabel="TFS parse tree"
                  />
                  <div className="row wrap">
                    {selectedLui && (
                      <>
                        <span className="muted small">
                          {selectedLui.entity} (edge {selectedLui.eid})
                        </span>
                        <button type="button" className="small" onClick={() => void showNode(selectedLui.id, 'avm')}>
                          AVM
                        </button>
                        <button type="button" className="small" onClick={() => void showNode(selectedLui.id, 'mrs')}>
                          MRS
                        </button>
                        <button
                          type="button"
                          className="small"
                          onClick={() => void lookup(selectedLui.children.length ? 'rule' : 'lex', selectedLui.entity)}
                        >
                          {selectedLui.children.length ? 'Rule definition' : 'Lexical entry'}
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
              {parse.count === 0 && <div className="warning">No parses.{parse.output && <pre className="code">{parse.output}</pre>}</div>}
            </>
          )}
        </section>

        <section className="card">
          <h3>Look up</h3>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault()
              void lookup(kind, name)
            }}
          >
            <select value={kind} onChange={(e) => setKind(e.target.value as LookupKind)} aria-label="What to look up">
              {(Object.keys(KIND_LABEL) as LookupKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
            <input className="grow" value={name} onChange={(e) => setName(e.target.value)} placeholder="name (or part of one)" aria-label="Name to look up" spellCheck={false} />
            <button type="submit">Show</button>
            {kind === 'type' && (
              <button type="button" disabled={!name.trim()} onClick={() => void hierarchy(name.trim())}>
                Hierarchy
              </button>
            )}
          </form>
          {matches && matches.names.length > 0 && (
            <div className="matches">
              <div className="muted small">
                {matches.names.length} matches{matches.more ? ` (${matches.more})` : ''}:
              </div>
              <ul>
                {matches.names.map((m) => (
                  <li key={m}>
                    <button type="button" className="link" onClick={() => void lookup(matches.kind, m)}>
                      {m}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {hier && (
          <section className="card">
            <div className="row">
              <h3 className="grow">Hierarchy around {hier.name}</h3>
              <button type="button" className="ghost" onClick={() => setHier(null)} aria-label="Close hierarchy">
                ✕
              </button>
            </div>
            <HierarchyView key={hier.name} nodes={hier.nodes} focus={hier.name} onSelect={(t) => void lookup('type', t)} />
          </section>
        )}
      </div>

      <div className="tfs-right">
        <div className={`unify-bar card${source ? ' active' : ''}`}>
          <strong>Interactive unification</strong>
          {!source ? (
            <span className="muted"> Click a feature name in one AVM, then in another, to unify the two substructures.</span>
          ) : (
            <span>
              {' '}
              <code>
                {panelTitle(source.panel)}: {source.path.join('.') || '(root)'}
              </code>{' '}
              ⊔{' '}
              {target ? (
                <code>
                  {panelTitle(target.panel)}: {target.path.join('.') || '(root)'}
                </code>
              ) : (
                <span className="muted">pick a target…</span>
              )}{' '}
              <button type="button" className="primary small" disabled={!target} onClick={() => void unify()}>
                Unify
              </button>{' '}
              <button type="button" className="small" onClick={() => (setSource(null), setTarget(null))}>
                Clear
              </button>
            </span>
          )}
        </div>
        {!panels.length && <div className="empty">Feature structures you open appear here.</div>}
        {panels.map((p) => (
          <section className="card avm-panel" key={p.key} data-testid="avm-panel">
            <div className="row">
              <h3 className="grow" title={p.source}>
                {p.source}
              </h3>
              {p.rootType && !p.rootType.startsWith('"') && (
                <button type="button" className="small" onClick={() => void hierarchy(p.rootType!)}>
                  Hierarchy
                </button>
              )}
              <button type="button" className="small" onClick={() => pickPath(p, [])} title="Use the whole AVM for unification">
                Select root
              </button>
              <button type="button" className="ghost" onClick={() => setPanels((ps) => ps.filter((x) => x.key !== p.key))} aria-label="Close">
                ✕
              </button>
            </div>
            {p.definition && (
              <div className="definition">
                <code>{p.definition.tdl}</code>{' '}
                {p.definition.path ? (
                  <button type="button" className="link small" onClick={() => navigate('files', { page: 'files', path: p.definition!.path!, line: p.definition!.line })}>
                    {p.definition.file}:{p.definition.line}
                  </button>
                ) : (
                  <span className="muted small">
                    {p.definition.file}:{p.definition.line}
                  </span>
                )}
              </div>
            )}
            {p.failure && (
              <div className="error">
                Unification failure at <code>{p.failure.path.join('.') || '(root)'}</code>: {p.failure.types.join(' ⊓ ')}
              </div>
            )}
            <AvmView
              avm={p.avm}
              failurePath={p.failure?.path ?? null}
              selectedPath={source?.panel === p.key ? source.path : target?.panel === p.key ? target.path : null}
              onPathClick={(path) => pickPath(p, path)}
            />
          </section>
        ))}
      </div>
    </div>
  )
}
