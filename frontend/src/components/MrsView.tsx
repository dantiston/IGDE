import { useMemo, useState } from 'react'
import type { DmrsJson, MrsJson } from '../types'

const ARG_ORDER = ['LBL', 'ARG0', 'ARG1', 'ARG2', 'ARG3', 'ARG4', 'ARG', 'RSTR', 'BODY', 'CARG']
const argRank = (a: string) => {
  const i = ARG_ORDER.indexOf(a)
  return i < 0 ? ARG_ORDER.length : i
}

function MrsAvm({ mrs }: { mrs: MrsJson }) {
  const [hot, setHot] = useState<string | null>(null)
  const seen = new Set<string>()
  const renderVar = (v: string) => {
    const info = mrs.variables?.[v]
    const props = info?.properties && Object.keys(info.properties).length ? info.properties : null
    const first = !seen.has(v)
    seen.add(v)
    const sort = (info?.type ?? v.replace(/\d+$/, '')).charAt(0)
    return (
      <span
        className={`mrs-var sort-${sort}${hot === v ? ' hot' : ''}`}
        onMouseEnter={() => setHot(v)}
        onMouseLeave={() => setHot(null)}
        title={props ? Object.entries(props).map(([k, x]) => `${k}: ${x}`).join('\n') : undefined}
      >
        {v}
        {first && props && (
          <span className="mrs-props">
            [{' '}
            {Object.entries(props).map(([k, x]) => (
              <span key={k}>
                {k}: <b>{x}</b>{' '}
              </span>
            ))}
            ]
          </span>
        )}
      </span>
    )
  }
  const isVar = (s: string) => /^[a-z]+\d+$/.test(s) && !!mrs.variables?.[s]
  return (
    <div className="mrs-avm">
      <div className="mrs-row">
        <span className="mrs-feat">TOP</span>
        {mrs.top ? renderVar(mrs.top) : '—'}
      </div>
      <div className="mrs-row">
        <span className="mrs-feat">INDEX</span>
        {mrs.index ? renderVar(mrs.index) : '—'}
      </div>
      <div className="mrs-row">
        <span className="mrs-feat">RELS</span>
        <span className="mrs-angle">⟨</span>
        <div className="mrs-rels">
          {mrs.relations.map((r, i) => {
            const args = Object.entries(r.arguments).sort((a, b) => argRank(a[0]) - argRank(b[0]))
            return (
              <div className="mrs-ep" key={i}>
                <div className="mrs-pred">
                  {r.predicate}
                  {r.lnk && <span className="mrs-lnk">⟨{r.lnk.from}:{r.lnk.to}⟩</span>}
                </div>
                <div className="mrs-row">
                  <span className="mrs-feat">LBL</span>
                  {renderVar(r.label)}
                </div>
                {args.map(([k, v]) => (
                  <div className="mrs-row" key={k}>
                    <span className="mrs-feat">{k}</span>
                    {isVar(v) ? renderVar(v) : <span className="mrs-const">“{v}”</span>}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
        <span className="mrs-angle">⟩</span>
      </div>
      <div className="mrs-row">
        <span className="mrs-feat">HCONS</span>
        <span className="mrs-angle">⟨</span>
        <span className="mrs-hcons">
          {(mrs.constraints ?? []).map((c, i) => (
            <span key={i} className="mrs-hcon">
              {renderVar(c.high)} <span className="mrs-qeq">{c.relation}</span> {renderVar(c.low)}
            </span>
          ))}
        </span>
        <span className="mrs-angle">⟩</span>
      </div>
    </div>
  )
}

export function DmrsGraph({ dmrs }: { dmrs: DmrsJson }) {
  const nodes = useMemo(
    () => [...dmrs.nodes].sort((a, b) => (a.lnk?.from ?? 0) - (b.lnk?.from ?? 0) || a.nodeid - b.nodeid),
    [dmrs],
  )
  const charW = 7
  const xs = new Map<number, number>()
  let x = 10
  const widths = nodes.map((n) => Math.max(60, (n.predicate.length + (n.carg ? n.carg.length + 3 : 0)) * charW + 16))
  nodes.forEach((n, i) => {
    xs.set(n.nodeid, x + widths[i] / 2)
    x += widths[i] + 14
  })
  const spanOf = (l: DmrsJson['links'][number]) => Math.abs((xs.get(l.from) ?? 0) - (xs.get(l.to) ?? 0))
  const maxSpan = Math.max(1, ...dmrs.links.map(spanOf))
  const arcTop = 30 + Math.min(160, maxSpan * 0.35)
  const baseY = arcTop + 30
  const width = x
  const height = baseY + 50
  return (
    <div className="tree-scroll">
      <svg className="dmrs" width={width} height={height} role="img" aria-label="DMRS graph">
        <defs>
          <marker id="dmrs-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="dmrs-arrowhead" />
          </marker>
        </defs>
        {dmrs.links.map((l, i) => {
          const x1 = xs.get(l.from) ?? 0
          const x2 = xs.get(l.to) ?? 0
          const h = Math.min(arcTop - 10, 18 + spanOf(l) * 0.35)
          const y = baseY - 12
          const mid = (x1 + x2) / 2
          const d = x1 === x2 ? `M${x1 - 6},${y} C${x1 - 30},${y - 50} ${x1 + 30},${y - 50} ${x1 + 6},${y}` : `M${x1},${y} C${x1},${y - h} ${x2},${y - h} ${x2},${y}`
          return (
            <g key={i}>
              <path d={d} className={`dmrs-link${l.post === 'EQ' ? ' eq' : ''}`} markerEnd="url(#dmrs-arrow)" />
              <text x={mid} y={y - h * 0.75 - 4} textAnchor="middle" className="dmrs-label">
                {l.rargname || ''}
                {l.post ? `/${l.post}` : ''}
              </text>
            </g>
          )
        })}
        {nodes.map((n, i) => {
          const cx = xs.get(n.nodeid) ?? 0
          const isTop = dmrs.top === n.nodeid
          return (
            <g key={n.nodeid} transform={`translate(${cx},${baseY})`}>
              <title>
                {[n.predicate, n.lnk ? `⟨${n.lnk.from}:${n.lnk.to}⟩` : '', ...Object.entries(n.sortinfo ?? {}).map(([k, v]) => `${k}=${v}`)]
                  .filter(Boolean)
                  .join(' ')}
              </title>
              <rect x={-widths[i] / 2} y={-12} width={widths[i]} height={24} rx={5} className={`dmrs-node${isTop ? ' top' : ''}`} />
              <text textAnchor="middle" y={4} className="dmrs-pred">
                {n.predicate}
                {n.carg ? ` (${n.carg})` : ''}
              </text>
              {isTop && (
                <text textAnchor="middle" y={28} className="dmrs-top">
                  TOP
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

const VIEWS = ['MRS', 'DMRS', 'SimpleMRS', 'DMRS text', 'EDS'] as const
type View = (typeof VIEWS)[number]

export function SemanticsPanel({
  mrs,
  simplemrs,
  dmrs,
  simpledmrs,
  eds,
}: {
  mrs?: MrsJson
  simplemrs?: string | null
  dmrs?: DmrsJson | null
  simpledmrs?: string | null
  eds?: string | null
}) {
  const available = VIEWS.filter((v) =>
    v === 'MRS' ? !!mrs : v === 'DMRS' ? !!dmrs : v === 'SimpleMRS' ? !!simplemrs : v === 'DMRS text' ? !!simpledmrs : !!eds,
  )
  const [view, setView] = useState<View>(available[0] ?? 'SimpleMRS')
  const text = view === 'SimpleMRS' ? simplemrs : view === 'DMRS text' ? simpledmrs : view === 'EDS' ? eds : null
  return (
    <div className="semantics">
      <div className="segmented" role="tablist">
        {available.map((v) => (
          <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? 'on' : ''} onClick={() => setView(v)}>
            {v}
          </button>
        ))}
        {text && (
          <button type="button" className="ghost" onClick={() => void navigator.clipboard?.writeText(text)}>
            Copy
          </button>
        )}
      </div>
      {view === 'MRS' && mrs && <MrsAvm mrs={mrs} />}
      {view === 'DMRS' && dmrs && <DmrsGraph dmrs={dmrs} />}
      {text && <pre className="code">{text}</pre>}
    </div>
  )
}
