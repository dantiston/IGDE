import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { Avm, AvmNode } from '../types'

/** Attribute-value matrix display for typed feature structures. */

const LIST_FEATS = ['FIRST', 'REST']
const isRef = (a: Avm): a is { ref: number } => 'ref' in a
const pathKey = (p: string[]) => p.join(' ')

interface ListView {
  items: { avm: Avm; path: string[] }[]
  tail: { avm: Avm; path: string[] } | null
}

/** Read a FIRST/REST chain as a list; null if *a* isn't a list cell. */
export function asList(a: Avm, path: string[]): ListView | null {
  const items: ListView['items'] = []
  let cur: Avm = a
  let curPath = path
  for (let guard = 0; guard < 10000; guard++) {
    if (isRef(cur)) return items.length ? { items, tail: { avm: cur, path: curPath } } : null
    const feats = cur.features.map(([f]) => f)
    if (feats.length === 2 && LIST_FEATS.every((f) => feats.includes(f)) && (cur.tag === null || cur === a)) {
      const first = cur.features.find(([f]) => f === 'FIRST')![1]
      items.push({ avm: first, path: [...curPath, 'FIRST'] })
      cur = cur.features.find(([f]) => f === 'REST')![1]
      curPath = [...curPath, 'REST']
      continue
    }
    if (!items.length) return null
    const end = !cur.features.length && /null|^\*?nil\*?$|^<\s*>$/i.test(cur.type) && cur.tag === null
    return { items, tail: end ? null : { avm: cur, path: curPath } }
  }
  return null
}

interface Ctx {
  isOpen: (path: string[], depth: number) => boolean
  toggle: (path: string[], depth: number) => void
  hoverTag: number | null
  setHoverTag: (t: number | null) => void
  listNotation: boolean
  failurePath: string | null
  selectedPath: string | null
  onPathClick?: (path: string[]) => void
}
const AvmCtx = createContext<Ctx | null>(null)

function Tag({ n }: { n: number }) {
  const c = useContext(AvmCtx)!
  return (
    <span
      className={`avm-tag${c.hoverTag === n ? ' hot' : ''}`}
      onMouseEnter={() => c.setHoverTag(n)}
      onMouseLeave={() => c.setHoverTag(null)}
    >
      {n}
    </span>
  )
}

function AvmValue({ avm, path, depth }: { avm: Avm; path: string[]; depth: number }) {
  const c = useContext(AvmCtx)!
  const key = pathKey(path)
  const marks = `${c.failurePath === key ? ' failure' : ''}${c.selectedPath === key ? ' selected' : ''}`
  if (isRef(avm)) {
    return (
      <span className={`avm-ref${marks}`}>
        <Tag n={avm.ref} />
      </span>
    )
  }
  const tag = avm.tag !== null ? <Tag n={avm.tag} /> : null
  if (c.listNotation) {
    const list = asList(avm, path)
    if (list) {
      return (
        <span className={`avm-list${marks}`}>
          {tag}
          <span className="avm-angle">⟨</span>
          {list.items.map((it, i) => (
            <span key={i} className="avm-list-item">
              {i > 0 && <span className="avm-comma">,</span>}
              <AvmValue avm={it.avm} path={it.path} depth={depth + 1} />
            </span>
          ))}
          {list.tail && (
            <span className="avm-list-item">
              <span className="avm-comma">…</span>
              <AvmValue avm={list.tail.avm} path={list.tail.path} depth={depth + 1} />
            </span>
          )}
          <span className="avm-angle">⟩</span>
        </span>
      )
    }
  }
  return <AvmBox node={avm} path={path} depth={depth} tag={tag} marks={marks} />
}

function AvmBox({
  node,
  path,
  depth,
  tag,
  marks,
}: {
  node: AvmNode
  path: string[]
  depth: number
  tag: React.ReactNode
  marks: string
}) {
  const c = useContext(AvmCtx)!
  const isString = node.type.startsWith('"')
  const typeEl = <span className={`avm-type${isString ? ' string' : ''}`}>{node.type}</span>
  if (!node.features.length) {
    return (
      <span className={`avm-atom${marks}`}>
        {tag}
        {typeEl}
      </span>
    )
  }
  const open = c.isOpen(path, depth)
  return (
    <span className={`avm-wrap${marks}`}>
      {tag}
      <span className={`avm${open ? '' : ' collapsed'}`}>
        <button
          type="button"
          className="avm-head"
          onClick={() => c.toggle(path, depth)}
          title={open ? 'Collapse' : `Expand (${node.features.length} features)`}
          aria-expanded={open}
        >
          {typeEl}
          {!open && <span className="avm-more"> […{node.features.length}]</span>}
        </button>
        {open &&
          node.features.map(([feat, val]) => {
            const p = [...path, feat]
            return (
              <span className="avm-row" key={feat}>
                {c.onPathClick ? (
                  <button
                    type="button"
                    className={`avm-feat clickable${c.selectedPath === pathKey(p) ? ' selected' : ''}`}
                    onClick={() => c.onPathClick!(p)}
                    title={p.join('.')}
                  >
                    {feat}
                  </button>
                ) : (
                  <span className="avm-feat" title={p.join('.')}>
                    {feat}
                  </span>
                )}
                <span className="avm-val">
                  <AvmValue avm={val} path={p} depth={depth + 1} />
                </span>
              </span>
            )
          })}
      </span>
    </span>
  )
}

export interface AvmViewProps {
  avm: Avm
  defaultDepth?: number
  failurePath?: string[] | null
  selectedPath?: string[] | null
  onPathClick?: (path: string[]) => void
}

export function AvmView({ avm, defaultDepth = 2, failurePath, selectedPath, onPathClick }: AvmViewProps) {
  const [depthLimit, setDepthLimit] = useState(defaultDepth)
  const [overrides, setOverrides] = useState<Record<string, boolean>>({})
  const [hoverTag, setHoverTag] = useState<number | null>(null)
  const [listNotation, setListNotation] = useState(true)

  // Always open the path to a unification failure or a selected node.
  const forced = useMemo(() => {
    const s = new Set<string>()
    for (const p of [failurePath, selectedPath]) {
      if (!p) continue
      for (let i = 0; i < p.length; i++) s.add(pathKey(p.slice(0, i)))
    }
    return s
  }, [failurePath, selectedPath])

  const isOpen = useCallback(
    (path: string[], depth: number) => {
      const k = pathKey(path)
      if (k in overrides) return overrides[k]
      return forced.has(k) || depth < depthLimit
    },
    [overrides, depthLimit, forced],
  )
  const toggle = useCallback(
    (path: string[], depth: number) => {
      const k = pathKey(path)
      setOverrides((o) => ({ ...o, [k]: !(k in o ? o[k] : forced.has(k) || depth < depthLimit) }))
    },
    [depthLimit, forced],
  )

  const ctx: Ctx = {
    isOpen,
    toggle,
    hoverTag,
    setHoverTag,
    listNotation,
    failurePath: failurePath ? pathKey(failurePath) : null,
    selectedPath: selectedPath ? pathKey(selectedPath) : null,
    onPathClick,
  }
  return (
    <div className="avm-view">
      <div className="avm-toolbar">
        <button type="button" onClick={() => (setOverrides({}), setDepthLimit(1000))}>
          Expand all
        </button>
        <button type="button" onClick={() => (setOverrides({}), setDepthLimit(1))}>
          Collapse
        </button>
        <label>
          <input type="checkbox" checked={listNotation} onChange={(e) => setListNotation(e.target.checked)} /> ⟨list⟩
          notation
        </label>
      </div>
      <div className="avm-scroll">
        <AvmCtx.Provider value={ctx}>
          <AvmValue avm={avm} path={[]} depth={0} />
        </AvmCtx.Provider>
      </div>
    </div>
  )
}
