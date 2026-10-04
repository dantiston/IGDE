/**
 * Test suites: create, edit, run and inspect [incr tsdb()] profiles.
 *
 * A test suite is a profile of test items (made here, or any existing
 * profile on disk, e.g. a grammar's gold profiles).  Running it with a
 * grammar makes a new profile (a "run") holding the processor's results, which can be
 * inspected item by item and compared with another run or with gold.
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { Modal } from '../components/Modal'
import { SemanticsPanel } from '../components/MrsView'
import { TreeView, fromParse } from '../components/Tree'
import { useFeed } from '../feed/FeedContext'
import { useAction, useApp } from '../state'
import type { CompareStatus, Comparison, ItemResults, Profile, ProfileRow, ProfileStats } from '../types'

const pct = (x: number | null | undefined) => (x === null || x === undefined ? '–' : `${(x * 100).toFixed(1)}%`)

const STATUS: Record<CompareStatus, { icon: string; label: string; help: string }> = {
  gained: { icon: '↑', label: 'gained', help: 'parses now, did not before' },
  lost: { icon: '↓', label: 'lost', help: 'no longer parses' },
  changed: { icon: '≠', label: 'changed', help: 'the other profile’s analysis is no longer among the results' },
  readings: { icon: '±', label: 'readings', help: 'same analysis, different number of readings' },
  same: { icon: '=', label: 'same', help: 'unchanged' },
  missing: { icon: '∅', label: 'missing', help: 'only in one of the profiles' },
}

function StatusBadge({ status }: { status: CompareStatus }) {
  const s = STATUS[status]
  return (
    <span className={`cmp cmp-${status}`} title={s.help}>
      <span aria-hidden>{s.icon}</span> {s.label}
    </span>
  )
}

function runLabel(p: Profile) {
  if (p.runStatus === 'running' && p.progress) return `${p.progress.done}/${p.progress.total}`
  if (p.runStatus === 'failed') return 'failed'
  if (p.runStatus === 'cancelled') return 'cancelled'
  return p.stats?.coverage !== null && p.stats?.coverage !== undefined ? pct(p.stats.coverage) : ''
}

/* ---- stats ---- */

function StatTile({ label, value, sub, delta }: { label: string; value: string; sub?: string; delta?: { value: number; goodUp: boolean; vs: string } | null }) {
  let deltaEl = null
  if (delta && Math.abs(delta.value) > 1e-9) {
    const up = delta.value > 0
    const good = up === delta.goodUp
    deltaEl = (
      <div className={`stat-delta ${good ? 'good' : 'bad'}`} title={`compared with ${delta.vs}`}>
        <span aria-hidden>{up ? '↑' : '↓'}</span> {up ? '+' : '−'}
        {Math.abs(delta.value * 100).toFixed(1)} pts vs {delta.vs}
      </div>
    )
  }
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
      {deltaEl}
    </div>
  )
}

function StatTiles({ stats, other, otherName }: { stats: ProfileStats; other: ProfileStats | null; otherName: string }) {
  const d = (a: number | null, b: number | null | undefined, goodUp: boolean) =>
    other && a !== null && b !== null && b !== undefined ? { value: a - b, goodUp, vs: otherName } : null
  return (
    <div className="stat-tiles" data-testid="stats">
      <StatTile label="Items" value={stats.items.toLocaleString()} sub={stats.illformed ? `${stats.illformed} ungrammatical` : 'all grammatical'} />
      <StatTile
        label="Coverage"
        value={pct(stats.coverage)}
        sub={stats.processed ? `${stats.parsed} of ${stats.processed} parsed` : 'not processed'}
        delta={d(stats.coverage, other?.coverage, true)}
      />
      {stats.illformed > 0 && (
        <StatTile label="Overgeneration" value={pct(stats.overgeneration)} sub="ungrammatical items parsed" delta={d(stats.overgeneration, other?.overgeneration, false)} />
      )}
      <StatTile label="Average readings" value={stats.avgReadings?.toString() ?? '–'} />
      <StatTile label="Average time" value={stats.avgTime !== null ? `${stats.avgTime} ms` : '–'} />
      <StatTile label="Errors" value={stats.errors.toString()} sub="timeouts, resource limits" />
    </div>
  )
}

/* ---- one item's results ---- */

function ResultsView({ data }: { data: ItemResults }) {
  const [selected, setSelected] = useState(0)
  const [rules, setRules] = useState(false)
  const result = data.results[selected]
  const tree = useMemo(() => (result?.derivation ? fromParse(result.derivation, result.tree, rules) : null), [result, rules])
  if (!data.processed) return <div className="muted">Not processed.</div>
  if (data.error) return <div className="error">{data.error}</div>
  if (!data.results.length) return <div className="warning">{(data.readings ?? 0) > 0 ? `${data.readings} readings, but no results were stored.` : 'No parses.'}</div>
  return (
    <>
      <div className="row wrap">
        {data.results.length > 1 && (
          <div className="result-tabs" role="tablist">
            {data.results.map((_, i) => (
              <button key={i} type="button" role="tab" aria-selected={selected === i} className={selected === i ? 'on' : ''} onClick={() => setSelected(i)}>
                #{i + 1}
              </button>
            ))}
          </div>
        )}
        <div className="segmented">
          <button type="button" className={!rules ? 'on' : ''} onClick={() => setRules(false)}>
            Labels
          </button>
          <button type="button" className={rules ? 'on' : ''} onClick={() => setRules(true)}>
            Rules
          </button>
        </div>
        <span className="muted small">
          {data.readings} reading{data.readings === 1 ? '' : 's'}
          {data.results.length < (data.readings ?? 0) ? `, ${data.results.length} stored` : ''}
        </span>
      </div>
      {tree && <TreeView root={tree} ariaLabel={`Result ${selected + 1}`} />}
      {result && <SemanticsPanel key={selected} mrs={result.mrs} simplemrs={result.simplemrs} dmrs={result.dmrs} simpledmrs={result.simpledmrs} eds={result.eds} />}
    </>
  )
}

function ItemDetail({ profile, other, row }: { profile: Profile; other: Profile | null; row: ProfileRow }) {
  const { navigate } = useApp()
  const feed = useFeed()
  const [which, setWhich] = useState<'this' | 'other'>('this')
  const [data, setData] = useState<{ this?: ItemResults; other?: ItemResults; error?: string }>({})
  const target = which === 'other' && other ? other : profile

  useEffect(() => {
    let stale = false
    if (data[which]) return
    api.profileItem(target.id, row.id).then(
      (r) => !stale && setData((d) => ({ ...d, [which]: r })),
      (e) => !stale && setData((d) => ({ ...d, error: (e as Error).message })),
    )
    return () => {
      stale = true
    }
  }, [which, target.id, row.id, data])

  return (
    <div className="item-detail" data-testid="item-detail">
      <div className="row wrap">
        {other && (
          <div className="segmented" role="tablist">
            <button type="button" role="tab" aria-selected={which === 'this'} className={which === 'this' ? 'on' : ''} onClick={() => setWhich('this')}>
              {profile.name}
            </button>
            <button type="button" role="tab" aria-selected={which === 'other'} className={which === 'other' ? 'on' : ''} onClick={() => setWhich('other')}>
              {other.name}
            </button>
          </div>
        )}
        <span className="grow" />
        <button
          type="button"
          className="small"
          onClick={() => {
            feed.parse(row.input)
            navigate('workbench')
          }}
        >
          Parse in Workbench
        </button>
      </div>
      {row.comment && <div className="muted small">{row.comment}</div>}
      {data.error && <div className="error">{data.error}</div>}
      {data[which] ? <ResultsView key={which} data={data[which]!} /> : !data.error && <div className="muted">Loading…</div>}
    </div>
  )
}

/* ---- items: table and editor ---- */

type Filter = 'all' | 'parsed' | 'unparsed' | 'errors' | 'illformed' | CompareStatus
const PAGE = 200

function ItemsTable({ profile, other, comparison }: { profile: Profile; other: Profile | null; comparison: Comparison | null }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  const [limit, setLimit] = useState(PAGE)
  const rows = profile.rows ?? []
  const processed = rows.some((r) => r.processed)
  const statusOf = (r: ProfileRow) => comparison?.items[String(r.id)]?.status

  const shown = rows.filter((r) => {
    const q = query.trim().toLowerCase()
    if (q && !r.input.toLowerCase().includes(q) && !String(r.id).includes(q)) return false
    switch (filter) {
      case 'all':
        return true
      case 'parsed':
        return (r.readings ?? 0) > 0
      case 'unparsed':
        return r.processed && !((r.readings ?? 0) > 0)
      case 'errors':
        return !!r.error
      case 'illformed':
        return !r.wf
      default:
        return statusOf(r) === filter
    }
  })
  const filters: { key: Filter; label: string; count: number }[] = [
    { key: 'all', label: 'All', count: rows.length },
    ...(processed
      ? ([
          { key: 'parsed', label: 'Parsed', count: rows.filter((r) => (r.readings ?? 0) > 0).length },
          { key: 'unparsed', label: 'Not parsed', count: rows.filter((r) => r.processed && !((r.readings ?? 0) > 0)).length },
          { key: 'errors', label: 'Errors', count: rows.filter((r) => r.error).length },
        ] as const)
      : []),
    { key: 'illformed', label: 'Ungrammatical', count: rows.filter((r) => !r.wf).length },
  ]

  return (
    <div>
      <div className="row wrap items-filters">
        <div className="segmented" role="tablist" aria-label="Show items">
          {filters.map((f) => (
            <button key={f.key} type="button" role="tab" aria-selected={filter === f.key} className={filter === f.key ? 'on' : ''} onClick={() => setFilter(f.key)}>
              {f.label} <span className="count">{f.count}</span>
            </button>
          ))}
        </div>
        {comparison && (
          <div className="segmented" role="tablist" aria-label="Show compared items">
            {(Object.keys(STATUS) as CompareStatus[])
              .filter((k) => comparison.counts[k])
              .map((k) => (
                <button key={k} type="button" role="tab" aria-selected={filter === k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)} title={STATUS[k].help}>
                  <StatusBadge status={k} /> <span className="count">{comparison.counts[k]}</span>
                </button>
              ))}
          </div>
        )}
        <input className="grow search" placeholder="Search items…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search items" />
      </div>
      <table className="table items-table">
        <thead>
          <tr>
            <th className="num">ID</th>
            <th>Input</th>
            {processed && <th className="num">Readings</th>}
            {processed && <th className="num">Time (ms)</th>}
            {comparison && <th>vs {other?.name}</th>}
            {processed && <th>Error</th>}
          </tr>
        </thead>
        <tbody>
          {shown.slice(0, limit).map((r) => {
            const st = statusOf(r)
            const cmp = comparison?.items[String(r.id)]
            return (
              <Fragment key={r.id}>
                <tr
                  className={`item-row${open === r.id ? ' open' : ''}${r.processed && !((r.readings ?? 0) > 0) && r.wf ? ' unparsed' : ''}`}
                  onClick={() => setOpen(open === r.id ? null : r.id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setOpen(open === r.id ? null : r.id)}
                  aria-expanded={open === r.id}
                >
                  <td className="num">{r.id}</td>
                  <td>
                    {!r.wf && <span className="ungrammatical" title="ungrammatical (i-wf 0)">*</span>}
                    {r.input}
                  </td>
                  {processed && <td className="num">{r.processed ? (r.readings ?? '–') : ''}</td>}
                  {processed && <td className="num">{r.processed && (r.time ?? -1) >= 0 ? r.time : ''}</td>}
                  {comparison && (
                    <td>
                      {st && <StatusBadge status={st} />}
                      {cmp && st !== 'same' && cmp.otherReadings !== null && <span className="muted small"> ({cmp.otherReadings} → {cmp.readings ?? '–'})</span>}
                    </td>
                  )}
                  {processed && <td className="error-cell">{r.error}</td>}
                </tr>
                {open === r.id && (
                  <tr className="detail-row">
                    <td colSpan={6}>
                      <ItemDetail profile={profile} other={other} row={r} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
      {shown.length > limit && (
        <button type="button" onClick={() => setLimit(limit + PAGE)}>
          Show more ({shown.length - limit} more)
        </button>
      )}
      {!shown.length && <div className="muted">No items.</div>}
    </div>
  )
}

interface EditRow {
  key: number
  id: number | null
  input: string
  wf: number
  comment: string
}

function ItemsEditor({ profile, onDone }: { profile: Profile; onDone: (p: Profile | null) => void }) {
  const [rows, setRows] = useState<EditRow[]>(() => (profile.rows ?? []).map((r, i) => ({ key: i, id: r.id, input: r.input, wf: r.wf, comment: r.comment })))
  const [bulk, setBulk] = useState('')
  const [nextKey, setNextKey] = useState(rows.length)
  const save = useAction(api.saveItems)
  const set = (key: number, patch: Partial<EditRow>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  const add = (items: { input: string; wf: number }[]) => {
    setRows((rs) => [...rs, ...items.map((it, i) => ({ key: nextKey + i, id: null, input: it.input, wf: it.wf, comment: '' }))])
    setNextKey(nextKey + items.length)
  }
  return (
    <div className="items-editor" data-testid="items-editor">
      {!!profile.stats?.processed && (
        <div className="warning">This profile has results; after editing its items they will no longer match. Run the suite again for new results.</div>
      )}
      <table className="table">
        <thead>
          <tr>
            <th className="num">ID</th>
            <th>Input</th>
            <th title="grammatical (i-wf)">Grammatical</th>
            <th>Comment</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="num muted">{r.id ?? 'new'}</td>
              <td>
                <input className="full" value={r.input} onChange={(e) => set(r.key, { input: e.target.value })} aria-label={`Item ${r.id ?? 'new'} input`} />
              </td>
              <td className="center">
                <input type="checkbox" checked={!!r.wf} onChange={(e) => set(r.key, { wf: e.target.checked ? 1 : 0 })} aria-label={`Item ${r.id ?? 'new'} is grammatical`} />
              </td>
              <td>
                <input className="full" value={r.comment} onChange={(e) => set(r.key, { comment: e.target.value })} aria-label={`Item ${r.id ?? 'new'} comment`} />
              </td>
              <td>
                <button type="button" className="ghost small" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))} aria-label={`Delete item ${r.id ?? 'new'}`}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row">
        <button type="button" onClick={() => add([{ input: '', wf: 1 }])}>
          + Add item
        </button>
      </div>
      <label className="field">
        <span>Add several (one per line; start a line with * for an ungrammatical item)</span>
        <textarea rows={3} value={bulk} onChange={(e) => setBulk(e.target.value)} aria-label="Add several items" spellCheck={false} />
      </label>
      <div className="row">
        <button
          type="button"
          disabled={!bulk.trim()}
          onClick={() => {
            add(
              bulk
                .split('\n')
                .map((l) => l.trim())
                .filter(Boolean)
                .map((l) => (l.startsWith('*') ? { input: l.slice(1).trim(), wf: 0 } : { input: l, wf: 1 })),
            )
            setBulk('')
          }}
        >
          Add lines
        </button>
        <span className="grow" />
        {save.error && <span className="error">{save.error}</span>}
        <button type="button" onClick={() => onDone(null)}>
          Discard
        </button>
        <button
          type="button"
          className="primary"
          disabled={save.busy}
          onClick={async () => {
            const r = await save.run(
              profile.id,
              rows.map((x) => ({ id: x.id, input: x.input, wf: x.wf, comment: x.comment })),
            )
            if (r) onDone(r.profile)
          }}
        >
          {save.busy ? 'Saving…' : 'Save items'}
        </button>
      </div>
    </div>
  )
}

/* ---- one profile ---- */

function ProfileView({ id, all, onChanged, onSelect }: { id: number; all: Profile[]; onChanged: () => void; onSelect: (id: number | null) => void }) {
  const { status, notify } = useApp()
  const listed = all.find((p) => p.id === id)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [n, setN] = useState('')
  const [compareTo, setCompareTo] = useState<number | null | undefined>(undefined)
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const grammar = status?.activeGrammar

  // reload when the list says the profile changed (e.g. a run finished)
  const listedKey = listed ? `${listed.runStatus}:${listed.progress?.done ?? ''}:${listed.stats?.processed ?? ''}:${listed.stats?.items ?? ''}` : ''
  useEffect(() => {
    let stale = false
    api.profile(id).then(
      (r) => {
        if (stale) return
        setProfile(r.profile)
        setError(null)
      },
      (e) => !stale && setError((e as Error).message),
    )
    return () => {
      stale = true
    }
  }, [id, listedKey])

  // compare a run with the previous run of its suite, or with the suite if it has results (e.g. gold)
  const candidates = all.filter((p) => p.id !== id && p.runStatus !== 'running' && (p.stats?.processed ?? 0) > 0)
  const defaultOther = useMemo(() => {
    if (!listed || listed.kind !== 'run') return null
    const siblings = all.filter((p) => p.kind === 'run' && p.suite === listed.suite && p.id < listed.id && (p.stats?.processed ?? 0) > 0).sort((a, b) => b.id - a.id)
    if (siblings[0]) return siblings[0].id
    const suite = all.find((p) => p.id === listed.suite)
    return suite && (suite.stats?.processed ?? 0) > 0 ? suite.id : null
  }, [all, listed])
  const otherId = compareTo === undefined ? defaultOther : compareTo
  const other = all.find((p) => p.id === otherId) ?? null

  useEffect(() => {
    setComparison(null)
    if (!other || !profile || profile.runStatus === 'running' || !(profile.stats?.processed ?? 0)) return
    let stale = false
    api.compareProfiles(profile.id, other.id).then(
      (c) => !stale && setComparison(c),
      (e) => !stale && notify((e as Error).message, 'error'),
    )
    return () => {
      stale = true
    }
  }, [other, profile, notify])

  if (error) return <div className="error">{error}</div>
  if (!profile) return <div className="muted">Loading…</div>

  const running = profile.runStatus === 'running'
  const suiteName = profile.kind === 'run' ? all.find((p) => p.id === profile.suite)?.name : null

  return (
    <div className="profile-view" data-testid="profile-view">
      <div className="card">
        <div className="row wrap">
          <h2 className="grow">
            {profile.name} <span className="badge">{profile.kind === 'run' ? 'run' : 'test suite'}</span>
          </h2>
          {profile.kind === 'suite' && !editing && (
            <>
              <input
                className="n-input"
                type="number"
                min={1}
                value={n}
                onChange={(e) => setN(e.target.value)}
                placeholder={String(status?.settings.maxResults ?? 5)}
                aria-label="Results per item"
                title="Results to keep per item"
              />
              <button
                type="button"
                className="primary"
                disabled={!grammar || !profile.exists}
                onClick={async () => {
                  try {
                    const r = await api.runProfile(profile.id, grammar?.id, n ? Number(n) : undefined)
                    notify(`Running ${profile.name} with ${grammar?.name}…`)
                    onChanged()
                    onSelect(r.profile.id)
                  } catch (e) {
                    notify((e as Error).message, 'error')
                  }
                }}
              >
                Run with {grammar?.name ?? '…'}
              </button>
              <button type="button" onClick={() => setEditing(true)} disabled={!profile.exists}>
                Edit items
              </button>
            </>
          )}
          {running && (
            <button type="button" onClick={() => void api.cancelRun(profile.id).then(onChanged)}>
              Cancel run
            </button>
          )}
          <button
            type="button"
            className="danger"
            onClick={async () => {
              const files = profile.owned
              if (!window.confirm(files ? `Delete the run “${profile.name}” and its files?` : `Remove “${profile.name}” from IGDE? (No files are deleted.)`)) return
              try {
                await api.removeProfile(profile.id, files)
                onSelect(null)
                onChanged()
              } catch (e) {
                notify((e as Error).message, 'error')
              }
            }}
          >
            {profile.owned ? 'Delete run' : 'Remove'}
          </button>
        </div>
        <dl className="kv">
          <dt>Profile</dt>
          <dd>
            <code>{profile.path}</code> {!profile.exists && <span className="badge warn">missing</span>}
          </dd>
          {suiteName && (
            <>
              <dt>Test suite</dt>
              <dd>
                <button type="button" className="link" onClick={() => onSelect(profile.suite)}>
                  {suiteName}
                </button>
              </dd>
            </>
          )}
          {profile.stats?.runInfo && (
            <>
              <dt>Processed</dt>
              <dd>
                {profile.stats.runInfo.grammar} with {profile.stats.runInfo.application}, {profile.stats.runInfo.start}
              </dd>
            </>
          )}
        </dl>
        {running && profile.progress && (
          <div className="run-progress" data-testid="run-progress">
            <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={profile.progress.total} aria-valuenow={profile.progress.done}>
              <div className="meter-fill" style={{ width: `${(100 * profile.progress.done) / Math.max(1, profile.progress.total)}%` }} />
            </div>
            <span className="muted small">
              {profile.progress.done} of {profile.progress.total} items
            </span>
          </div>
        )}
        {(profile.runStatus === 'failed' || profile.runStatus === 'cancelled') && (
          <details className={profile.runStatus === 'failed' ? 'error' : 'warning'} open={profile.runStatus === 'failed'}>
            <summary>Run {profile.runStatus}</summary>
            <pre className="code log">{profile.runLog}</pre>
          </details>
        )}
        {profile.stats && !profile.stats.error && (
          <StatTiles stats={profile.stats} other={comparison && other?.stats ? other.stats : null} otherName={other?.name ?? ''} />
        )}
        {profile.stats?.error && <div className="error">{profile.stats.error}</div>}
      </div>

      {!editing && (profile.stats?.processed ?? 0) > 0 && (
        <div className="row compare-row">
          <label className="row">
            <span>Compare with</span>
            <select value={otherId ?? ''} onChange={(e) => setCompareTo(e.target.value ? Number(e.target.value) : null)} aria-label="Compare with">
              <option value="">nothing</option>
              {candidates.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.kind === 'run' ? `${all.find((s) => s.id === p.suite)?.name ?? '?'} · ${p.name}` : p.name}
                </option>
              ))}
            </select>
          </label>
          {other && !comparison && <span className="muted small">Comparing…</span>}
        </div>
      )}

      <div className="card">
        {editing ? (
          <ItemsEditor
            profile={profile}
            onDone={(p) => {
              setEditing(false)
              if (p) {
                setProfile(p)
                notify('Items saved', 'success')
                onChanged()
              }
            }}
          />
        ) : running ? (
          <div className="muted">Results appear here when the run finishes.</div>
        ) : (
          <ItemsTable key={`${profile.id}:${otherId ?? ''}`} profile={profile} other={comparison ? other : null} comparison={comparison} />
        )}
      </div>
    </div>
  )
}

/* ---- creating / adding ---- */

function NewSuite({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Profile) => void }) {
  const [tab, setTab] = useState<'new' | 'existing'>('new')
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [directory, setDirectory] = useState('')
  const [picking, setPicking] = useState(false)
  const act = useAction(async (fn: () => Promise<{ profile: Profile }>) => onCreated((await fn()).profile))
  return (
    <Modal title="Add a test suite" onClose={onClose}>
      <div className="segmented" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'new'} className={tab === 'new' ? 'on' : ''} onClick={() => setTab('new')}>
          New test suite
        </button>
        <button type="button" role="tab" aria-selected={tab === 'existing'} className={tab === 'existing' ? 'on' : ''} onClick={() => setTab('existing')}>
          Existing profile
        </button>
      </div>
      {tab === 'new' && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void act.run(() => api.createSuite(name.trim(), text, directory.trim() || undefined))
          }}
        >
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Test suite name" />
          </label>
          <label className="field">
            <span>Test items</span>
            <textarea
              rows={8}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={'One sentence per line.\n*Start a line with an asterisk for an ungrammatical item.\n; lines starting with ; or # are ignored'}
              aria-label="Test items"
              spellCheck={false}
            />
          </label>
          <label className="field">
            <span>Folder (optional)</span>
            <div className="row">
              <input value={directory} onChange={(e) => setDirectory(e.target.value)} placeholder="default: IGDE’s testsuites folder" spellCheck={false} aria-label="Test suite folder" />
              <button type="button" onClick={() => setPicking(!picking)}>
                Browse…
              </button>
            </div>
            <small className="muted">The profile is created in a new sub-folder named after the test suite.</small>
          </label>
          {picking && (
            <FileBrowser
              mode="pick-dir"
              onPick={(p) => {
                setDirectory(p)
                setPicking(false)
              }}
            />
          )}
          {act.error && <div className="error">{act.error}</div>}
          <div className="row end">
            <button type="submit" className="primary" disabled={act.busy || !name.trim() || !text.trim()}>
              Create test suite
            </button>
          </div>
        </form>
      )}
      {tab === 'existing' && (
        <>
          <p className="muted">
            Choose an [incr tsdb()] profile folder (one with a <code>relations</code> file), e.g. a test suite skeleton or a gold profile in a
            grammar’s <code>tsdb/</code> folder.
          </p>
          {act.error && <div className="error">{act.error}</div>}
          <FileBrowser
            mode="pick-dir"
            dirActions={(l) => (
              <button type="button" className="primary" disabled={act.busy} onClick={() => void act.run(() => api.addProfile(l.path))}>
                Add this profile
              </button>
            )}
          />
        </>
      )}
    </Modal>
  )
}

/* ---- the page ---- */

export function TestSuitesPage() {
  const [profiles, setProfiles] = useState<Profile[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  const load = useCallback(async () => {
    try {
      const r = await api.profiles()
      setProfiles(r.profiles)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])
  useEffect(() => {
    void load()
  }, [load])

  // poll while a run is going
  const running = profiles?.some((p) => p.runStatus === 'running')
  useEffect(() => {
    if (!running) return
    const t = window.setInterval(() => void load(), 1000)
    return () => window.clearInterval(t)
  }, [running, load])

  const suites = (profiles ?? []).filter((p) => p.kind === 'suite')
  const runsOf = (sid: number | null) => (profiles ?? []).filter((p) => p.kind === 'run' && p.suite === sid).sort((a, b) => b.id - a.id)
  const orphans = (profiles ?? []).filter((p) => p.kind === 'run' && !suites.some((s) => s.id === p.suite))
  const sel = selected ?? suites[0]?.id ?? null

  const profileRow = (p: Profile, depth: number) => (
    <button
      type="button"
      className={`tree-row profile${sel === p.id ? ' on' : ''}`}
      style={{ paddingLeft: 8 + depth * 16 }}
      onClick={() => setSelected(p.id)}
      title={p.path}
    >
      <span className="profile-name">{p.name}</span>
      {runLabel(p) && <span className={`badge run-${p.runStatus}`}>{runLabel(p)}</span>}
    </button>
  )

  return (
    <div className="page grammars-page testsuites-page">
      <aside className="explorer card">
        <div className="row">
          <h3 className="grow explorer-title">Test suites</h3>
          <button type="button" className="primary small" onClick={() => setAdding(true)}>
            + Add test suite
          </button>
        </div>
        {error && <div className="error">{error}</div>}
        {profiles && !profiles.length && <div className="empty small">No test suites yet.</div>}
        <ul className="explorer-tree" aria-label="Test suites">
          {suites.map((s) => {
            const runs = runsOf(s.id)
            const isOpen = !collapsed.has(s.id)
            return (
              <li key={s.id} data-testid={`suite-${s.id}`}>
                <div className="row suite-row">
                  <button
                    type="button"
                    className="caret-btn"
                    disabled={!runs.length}
                    aria-label={`${isOpen ? 'Hide' : 'Show'} runs of ${s.name}`}
                    onClick={() =>
                      setCollapsed((c) => {
                        const next = new Set(c)
                        if (next.has(s.id)) next.delete(s.id)
                        else next.add(s.id)
                        return next
                      })
                    }
                  >
                    {runs.length ? (isOpen ? '▾' : '▸') : ' '}
                  </button>
                  {profileRow(s, 0)}
                </div>
                {isOpen && runs.length > 0 && (
                  <ul>
                    {runs.map((r) => (
                      <li key={r.id}>{profileRow(r, 1)}</li>
                    ))}
                  </ul>
                )}
              </li>
            )
          })}
          {orphans.length > 0 && (
            <li>
              <div className="muted small tree-note">Runs of removed test suites</div>
              <ul>
                {orphans.map((r) => (
                  <li key={r.id}>{profileRow(r, 1)}</li>
                ))}
              </ul>
            </li>
          )}
        </ul>
      </aside>
      <section className="grammars-main">
        {sel !== null && profiles ? (
          <ProfileView key={sel} id={sel} all={profiles} onChanged={() => void load()} onSelect={setSelected} />
        ) : (
          profiles && (
            <div className="empty">
              Create a test suite of sentences, or add an existing [incr tsdb()] profile, then run it with a grammar to check coverage and
              compare runs.{' '}
              <button type="button" className="primary" onClick={() => setAdding(true)}>
                Add a test suite
              </button>
            </div>
          )
        )}
      </section>
      {adding && (
        <NewSuite
          onClose={() => setAdding(false)}
          onCreated={(p) => {
            setAdding(false)
            setSelected(p.id)
            void load()
          }}
        />
      )}
    </div>
  )
}
