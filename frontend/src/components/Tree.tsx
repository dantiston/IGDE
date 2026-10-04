import { useMemo } from 'react'
import type { DerivationNode, LabelledNode } from '../types'

/** Generic display tree: what all of IGDE's tree views are converted to. */
export interface TNode {
  key: string
  label: string
  sub?: string
  form?: string
  title?: string
  children: TNode[]
}

const CHAR_W = 7.4
const PAD = 14
const LEVEL_H = 46
const WORD_GAP = 30

interface Placed {
  node: TNode
  x: number
  y: number
  w: number
  children: Placed[]
}

function textWidth(s: string | undefined) {
  return (s?.length ?? 0) * CHAR_W
}

export function layoutTree(root: TNode) {
  const ownWidth = (n: TNode) => Math.max(textWidth(n.label), textWidth(n.sub), textWidth(n.form)) + PAD
  const measure = (n: TNode): number =>
    n.children.length ? Math.max(ownWidth(n), n.children.reduce((s, c) => s + measure(c), 0)) : ownWidth(n)
  const depthOf = (n: TNode): number => (n.children.length ? 1 + Math.max(...n.children.map(depthOf)) : 0)
  const total = measure(root)
  const wordY = (depthOf(root) + 1) * LEVEL_H + WORD_GAP
  const place = (n: TNode, left: number, depth: number): Placed => {
    const own = ownWidth(n)
    const y = depth * LEVEL_H + 20
    if (!n.children.length) return { node: n, x: left + own / 2, y, w: own, children: [] }
    const widths = n.children.map(measure)
    const sum = widths.reduce((a, b) => a + b, 0)
    let cursor = left + Math.max(0, (own - sum) / 2)
    const children = n.children.map((c, i) => {
      const p = place(c, cursor, depth + 1)
      cursor += widths[i]
      return p
    })
    const x = (children[0].x + children[children.length - 1].x) / 2
    return { node: n, x, y, w: own, children }
  }
  const placed = place(root, 0, 0)
  return { placed, width: total, height: wordY + 24, wordY }
}

interface TreeProps {
  root: TNode
  selected?: string | null
  onSelect?: (node: TNode) => void
  ariaLabel?: string
}

export function TreeView({ root, selected, onSelect, ariaLabel }: TreeProps) {
  const { placed, width, height, wordY } = useMemo(() => layoutTree(root), [root])
  const items: React.ReactNode[] = []
  const walk = (p: Placed) => {
    for (const c of p.children) {
      items.push(
        <line key={`e-${p.node.key}-${c.node.key}`} className="tree-edge" x1={p.x} y1={p.y + 8} x2={c.x} y2={c.y - 12} />,
      )
      walk(c)
    }
    const isSel = selected === p.node.key
    items.push(
      <g
        key={`n-${p.node.key}`}
        className={`tree-node${onSelect ? ' clickable' : ''}${isSel ? ' selected' : ''}`}
        transform={`translate(${p.x},${p.y})`}
        onClick={onSelect ? () => onSelect(p.node) : undefined}
        role={onSelect ? 'button' : undefined}
        tabIndex={onSelect ? 0 : undefined}
        aria-label={onSelect ? `${p.node.label}${p.node.sub ? ` (${p.node.sub})` : ''}` : undefined}
        aria-pressed={onSelect ? isSel : undefined}
        onKeyDown={
          onSelect
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(p.node)
                }
              }
            : undefined
        }
      >
        {p.node.title && <title>{p.node.title}</title>}
        <rect x={-p.w / 2 + 3} y={-14} width={p.w - 6} height={p.node.sub ? 30 : 20} rx={4} className="tree-box" />
        <text className="tree-label" textAnchor="middle" y={0}>
          {p.node.label}
        </text>
        {p.node.sub && (
          <text className="tree-sub" textAnchor="middle" y={12}>
            {p.node.sub}
          </text>
        )}
      </g>,
    )
    if (p.node.form !== undefined) {
      items.push(
        <g key={`w-${p.node.key}`}>
          <line className="tree-edge word" x1={p.x} y1={p.y + (p.node.sub ? 18 : 8)} x2={p.x} y2={wordY - 14} />
          <text className="tree-word" textAnchor="middle" x={p.x} y={wordY}>
            {p.node.form}
          </text>
        </g>,
      )
    }
  }
  walk(placed)
  return (
    <div className="tree-scroll">
      <svg className="tree" width={width} height={height} role="img" aria-label={ariaLabel ?? 'tree'}>
        {items}
      </svg>
    </div>
  )
}

/* ---- adapters ---- */

const isLeaf = (n: LabelledNode) => n.form !== undefined && !n.children?.length

/**
 * A parse/realization tree.  Nodes follow the derivation (so a node's key,
 * its path of daughter indices like "0.1.0", identifies the same edge in
 * ACE's TFS chart), labelled with ACE's node labels (S, NP, ...) where the
 * labelled tree lines up with the derivation, and with rule/lexical entry
 * names otherwise or when `rules` is set.
 */
export function fromParse(d: DerivationNode, labelled: LabelledNode | null, rules: boolean, path = '0'): TNode {
  const kids = d.daughters ?? []
  const labelKids = labelled?.children?.filter((c) => !isLeaf(c)) ?? []
  const aligned = labelled !== null && labelKids.length === kids.length
  // grammars without node-label templates get "?" for every node from ACE
  const label = !rules && labelled?.label && labelled.label !== '?' ? labelled.label : d.entity
  return {
    key: path,
    label,
    sub: label !== d.entity ? d.entity : d.type,
    form: d.form,
    title: [d.entity, d.id !== undefined ? `edge ${d.id}` : '', d.score !== undefined ? `score ${d.score}` : '', d.start !== undefined ? `${d.start}–${d.end}` : '']
      .filter(Boolean)
      .join(' · '),
    children: kids.map((k, i) => fromParse(k, aligned ? labelKids[i] : null, rules, `${path}.${i}`)),
  }
}

/** "0.1.0" -> [1, 0]: daughter indices below the root. */
export const pathOfKey = (key: string) => key.split('.').slice(1).map(Number)
