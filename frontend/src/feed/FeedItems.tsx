import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AvmView } from '../components/AvmView'
import { HierarchyView } from '../components/HierarchyView'
import { SemanticsPanel } from '../components/MrsView'
import { TreeView, fromParse, pathOfKey } from '../components/Tree'
import { ResponseMessages } from '../pages/common'
import { useApp } from '../state'
import { KIND_LABEL, useFeed } from './FeedContext'
import type { FeedItem, ItemOf } from './FeedContext'

function Card({
  item,
  kind,
  title,
  meta,
  children,
}: {
  item: FeedItem
  kind: string
  title: ReactNode
  meta?: ReactNode
  children: ReactNode
}) {
  const { remove } = useFeed()
  const [open, setOpen] = useState(true)
  return (
    <article className={`feed-item card kind-${item.kind}`} data-testid={`feed-${item.kind}`} id={`feed-item-${item.id}`}>
      <header className="feed-head">
        <button type="button" className="ghost feed-toggle" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={open ? 'Collapse' : 'Expand'}>
          {open ? '▾' : '▸'}
        </button>
        <span className={`feed-kind kind-${item.kind}`}>{kind}</span>
        <span className="feed-title">{title}</span>
        <span className="feed-meta muted small">
          {meta}
          {meta ? ' · ' : ''}
          {item.grammarName} · {new Date(item.time).toLocaleTimeString()}
        </span>
        <button type="button" className="ghost" onClick={() => remove(item.id)} aria-label="Remove from feed">
          ✕
        </button>
      </header>
      {open && <div className="feed-body">{children}</div>}
    </article>
  )
}

function Pending({ state }: { state: { status: string; error?: string } }) {
  if (state.status === 'loading') return <div className="muted pending">Working…</div>
  if (state.status === 'error') return <div className="error">{state.error}</div>
  return null
}

function ResultTabs({ count, selected, onSelect, probs }: { count: number; selected: number; onSelect: (i: number) => void; probs: (number | null)[] }) {
  if (count < 2) return null
  return (
    <div className="result-tabs" role="tablist" aria-label="Results">
      {Array.from({ length: count }, (_, i) => (
        <button key={i} type="button" role="tab" aria-selected={selected === i} className={selected === i ? 'on' : ''} onClick={() => onSelect(i)}>
          #{i + 1}
          {probs[i] !== null && probs[i] !== undefined && <span className="prob">{(probs[i]! * 100).toFixed(1)}%</span>}
        </button>
      ))}
    </div>
  )
}

function ParseCard({ item }: { item: ItemOf<'parse'> }) {
  const { generate, inspectNode } = useFeed()
  const [selected, setSelected] = useState(0)
  const [rules, setRules] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  const data = item.state.status === 'done' ? item.state.data : null
  const result = data?.results[selected]
  const tree = useMemo(() => (result?.derivation ? fromParse(result.derivation, result.tree, rules) : null), [result, rules])
  const readings = data ? (data.readings ?? data.results.length) : null
  return (
    <Card
      item={item}
      kind="Parse"
      title={`“${item.sentence}”`}
      meta={data ? `${readings} reading${readings === 1 ? '' : 's'}${data.time !== null ? ` · ${data.time} ms` : ''}` : undefined}
    >
      <Pending state={item.state} />
      {data && (
        <>
          <ResponseMessages r={data} />
          {!data.results.length && !data.error && <div className="warning">No parses.</div>}
          <ResultTabs count={data.results.length} selected={selected} onSelect={(i) => (setSelected(i), setPicked(null))} probs={data.results.map((r) => r.probability)} />
          {result && (
            <>
              <div className="row wrap">
                <div className="segmented">
                  <button type="button" className={!rules ? 'on' : ''} onClick={() => setRules(false)}>
                    Labels
                  </button>
                  <button type="button" className={rules ? 'on' : ''} onClick={() => setRules(true)}>
                    Rules
                  </button>
                </div>
                <span className="muted small grow">Click a node to add its feature structure to the feed.</span>
                <button
                  type="button"
                  disabled={!result.mrsString}
                  onClick={() => generate(result.simplemrs ?? result.mrsString ?? '', `“${item.sentence}” #${selected + 1}`)}
                >
                  Generate from this MRS
                </button>
              </div>
              {tree && (
                <TreeView
                  root={tree}
                  selected={picked}
                  ariaLabel={`Parse tree ${selected + 1} of “${item.sentence}”`}
                  onSelect={(n) => {
                    setPicked(n.key)
                    void inspectNode(item, selected, pathOfKey(n.key), n.label)
                  }}
                />
              )}
              <SemanticsPanel key={selected} mrs={result.mrs} simplemrs={result.simplemrs} dmrs={result.dmrs} simpledmrs={result.simpledmrs} eds={result.eds} />
            </>
          )}
        </>
      )}
    </Card>
  )
}

function GenerateCard({ item }: { item: ItemOf<'generate'> }) {
  const { parse } = useFeed()
  const [selected, setSelected] = useState(0)
  const [rules, setRules] = useState(false)
  const data = item.state.status === 'done' ? item.state.data : null
  const result = data?.results[selected]
  const tree = useMemo(() => (result?.derivation ? fromParse(result.derivation, result.tree, rules) : null), [result, rules])
  return (
    <Card
      item={item}
      kind="Generate"
      title={item.origin === 'pasted MRS' ? 'pasted MRS' : <>from {item.origin}</>}
      meta={data ? `${data.results.length} realization${data.results.length === 1 ? '' : 's'}` : undefined}
    >
      <details className="mrs-details">
        <summary className="muted small">Input MRS</summary>
        <pre className="code">{item.mrs}</pre>
      </details>
      <Pending state={item.state} />
      {data && (
        <>
          <ResponseMessages r={data} />
          {!data.results.length && !data.error && <div className="warning">No realizations.</div>}
          <ol className="realizations">
            {data.results.map((r, i) => (
              <li key={i} className={selected === i ? 'on' : ''}>
                <button type="button" className="realization" onClick={() => setSelected(i)} aria-pressed={selected === i}>
                  {r.surface}
                </button>
                {r.probability !== null && <span className="prob">{(r.probability * 100).toFixed(1)}%</span>}
                <button type="button" className="small ghost" onClick={() => parse(r.surface)}>
                  Parse
                </button>
              </li>
            ))}
          </ol>
          {tree && (
            <>
              <div className="segmented">
                <button type="button" className={!rules ? 'on' : ''} onClick={() => setRules(false)}>
                  Labels
                </button>
                <button type="button" className={rules ? 'on' : ''} onClick={() => setRules(true)}>
                  Rules
                </button>
              </div>
              <TreeView root={tree} ariaLabel={`Realization tree ${selected + 1}`} />
            </>
          )}
        </>
      )}
    </Card>
  )
}

function AvmCard({ item }: { item: ItemOf<'avm'> }) {
  const { navigate } = useApp()
  const { hierarchy, pickPath, unifySource, unifyTarget } = useFeed()
  const { doc } = item
  const selectedPath = unifySource?.itemId === item.id ? unifySource.path : unifyTarget?.itemId === item.id ? unifyTarget.path : null
  return (
    <Card
      item={item}
      kind={doc.failure ? 'Unify ✗' : item.title === 'Unification' ? 'Unify ✓' : 'AVM'}
      title={item.title}
      meta={item.origin !== 'lookup' ? item.origin : undefined}
    >
      <div className="row wrap">
        {doc.definition && (
          <span className="definition grow">
            <code>{doc.definition.tdl}</code>{' '}
            {doc.definition.path ? (
              <button type="button" className="link small" onClick={() => navigate('files', { page: 'files', path: doc.definition!.path!, line: doc.definition!.line })}>
                {doc.definition.file}:{doc.definition.line}
              </button>
            ) : (
              <span className="muted small">
                {doc.definition.file}:{doc.definition.line}
              </span>
            )}
          </span>
        )}
        <span className="grow" />
        {item.rootType && !item.rootType.startsWith('"') && (
          <button type="button" className="small" onClick={() => hierarchy(item.rootType!, item.grammarId)}>
            Hierarchy of {item.rootType}
          </button>
        )}
        <button type="button" className="small" onClick={() => pickPath({ itemId: item.id, path: [] })} title="Use the whole feature structure for unification">
          Select for unification
        </button>
      </div>
      {doc.failure && (
        <div className="error">
          Unification failure at <code>{doc.failure.path.join('.') || '(root)'}</code>: {doc.failure.types.join(' ⊓ ')}
        </div>
      )}
      <AvmView
        avm={doc.avm}
        failurePath={doc.failure?.path ?? null}
        selectedPath={selectedPath}
        onPathClick={(path) => pickPath({ itemId: item.id, path })}
      />
    </Card>
  )
}

function LookupCard({ item }: { item: ItemOf<'lookup'> }) {
  const { lookup } = useFeed()
  return (
    <Card item={item} kind="Look up" title={`${KIND_LABEL[item.lookupKind]} “${item.name}”`} meta={`${item.matches.length} matches${item.more ? ` (${item.more})` : ''}`}>
      <ul className="matches">
        {item.matches.map((m) => (
          <li key={m}>
            <button type="button" className="link" onClick={() => void lookup(item.lookupKind, m, item.grammarId)}>
              {m}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function HierarchyCard({ item }: { item: ItemOf<'hierarchy'> }) {
  const { lookup } = useFeed()
  return (
    <Card item={item} kind="Hierarchy" title={item.type}>
      <Pending state={item.state} />
      {item.state.status === 'done' && (
        <HierarchyView nodes={item.state.data} focus={item.type} onSelect={(t) => void lookup('type', t, item.grammarId)} />
      )}
    </Card>
  )
}

export function FeedItemView({ item }: { item: FeedItem }) {
  switch (item.kind) {
    case 'parse':
      return <ParseCard item={item} />
    case 'generate':
      return <GenerateCard item={item} />
    case 'avm':
      return <AvmCard item={item} />
    case 'lookup':
      return <LookupCard item={item} />
    case 'hierarchy':
      return <HierarchyCard item={item} />
  }
}
