import { useState } from 'react'
import type { HierarchyNode } from '../types'

/** The type hierarchy around one type, as reported by ACE (all of its
 * ancestors and descendants).  Grammars use multiple inheritance, so rather
 * than unfolding the whole DAG from the top type (which repeats types many
 * times) we show two trees rooted at the focus type: supertypes going up,
 * subtypes going down, each expanded on demand. */
export function HierarchyView({
  nodes,
  focus,
  onSelect,
}: {
  nodes: HierarchyNode[]
  focus: string
  onSelect?: (type: string) => void
}) {
  const focusIdx = nodes.findIndex((n) => n.name === focus)
  // expanded nodes, keyed by direction and tree path ("up:3/7/9")
  const [open, setOpen] = useState<Set<string>>(() => new Set())
  if (focusIdx < 0) return <div className="muted">Type {focus} not found.</div>

  const toggle = (k: string) =>
    setOpen((s) => {
      const next = new Set(s)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })

  const branch = (dir: 'up' | 'down', i: number, trail: number[]): React.ReactNode => {
    const n = nodes[i]
    const next = (dir === 'up' ? n.parents : n.children).filter((c) => !trail.includes(c))
    return (
      <ul>
        {next.map((c) => {
          const childKey = `${dir}:${[...trail, c].join('/')}`
          const more = (dir === 'up' ? nodes[c].parents : nodes[c].children).length
          return (
            <li key={c}>
              <span className="hier-node">
                {more ? (
                  <button
                    type="button"
                    className="hier-toggle"
                    aria-label={open.has(childKey) ? 'Collapse' : 'Expand'}
                    onClick={() => toggle(childKey)}
                  >
                    {open.has(childKey) ? '▾' : '▸'}
                  </button>
                ) : (
                  <span className="hier-toggle" />
                )}
                <button type="button" className="link" onClick={() => onSelect?.(nodes[c].name)}>
                  {nodes[c].name}
                </button>
                {more > 0 && !open.has(childKey) && (
                  <span className="muted small">
                    {' '}
                    {more} {dir === 'up' ? 'supertype' : 'subtype'}
                    {more === 1 ? '' : 's'}
                  </span>
                )}
              </span>
              {open.has(childKey) && branch(dir, c, [...trail, c])}
            </li>
          )
        })}
        {trail.length === 1 && !next.length && <li className="muted small">none</li>}
      </ul>
    )
  }

  const n = nodes[focusIdx]
  return (
    <div className="hierarchy">
      <div className="hier-section">
        <div className="muted small">
          Supertypes ({n.parents.length} immediate, {nodes.filter((_, i) => i !== focusIdx).length - countDescendants(nodes, focusIdx)} in all)
        </div>
        {branch('up', focusIdx, [focusIdx])}
      </div>
      <div className="hier-node focus">
        <button type="button" className="link" onClick={() => onSelect?.(n.name)}>
          {n.name}
        </button>
      </div>
      <div className="hier-section">
        <div className="muted small">
          Subtypes ({n.children.length} immediate, {countDescendants(nodes, focusIdx)} in all)
        </div>
        {branch('down', focusIdx, [focusIdx])}
      </div>
    </div>
  )
}

function countDescendants(nodes: HierarchyNode[], i: number) {
  const seen = new Set<number>()
  const walk = (j: number) => {
    for (const c of nodes[j].children) {
      if (!seen.has(c)) {
        seen.add(c)
        walk(c)
      }
    }
  }
  walk(i)
  return seen.size
}
