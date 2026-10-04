/**
 * Grammars: an IDE-style explorer of the user's grammars and their files
 * (plus the rest of the disk), with the editor and each grammar's details
 * (compile, log, activate) in the main pane.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { FileEditor } from '../components/FileEditor'
import { Modal } from '../components/Modal'
import { useAction, useApp } from '../state'
import type { FsEntry, Grammar } from '../types'

type Selection = { kind: 'grammar'; id: number } | { kind: 'file'; path: string; line?: number } | null
type GrammarFile = { path: string; rel: string; size: number }
type FileList = { status: 'loading' } | { status: 'done'; files: GrammarFile[] } | { status: 'error'; error: string }

function formatBytes(n: number | null) {
  if (n === null) return ''
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${(n / 1024).toFixed(1)} KB`
}

const dirname = (p: string) => p.slice(0, Math.max(1, p.lastIndexOf('/')))

/** The registered grammar whose directory contains *path* (deepest wins). */
function owningGrammar(grammars: Grammar[], path: string) {
  return grammars
    .filter((g) => path === g.rootDir || path.startsWith(g.rootDir + '/'))
    .sort((a, b) => b.rootDir.length - a.rootDir.length)[0]
}

function CompileBadge({ g }: { g: Grammar }) {
  if (g.kind === 'image') return <span className="badge">image</span>
  const label = { idle: 'not compiled', running: 'compiling…', ok: 'compiled', failed: 'compile failed' }[g.compileStatus]
  return <span className={`badge compile-${g.compileStatus}`}>{label}</span>
}

/* ---- explorer: grammars and their file trees ---- */

interface Dir {
  dirs: Map<string, Dir>
  files: GrammarFile[]
}

function buildTree(files: GrammarFile[]): Dir {
  const root: Dir = { dirs: new Map(), files: [] }
  for (const f of files) {
    const parts = f.rel.split('/')
    let d = root
    for (const part of parts.slice(0, -1)) {
      if (!d.dirs.has(part)) d.dirs.set(part, { dirs: new Map(), files: [] })
      d = d.dirs.get(part)!
    }
    d.files.push(f)
  }
  return root
}

function FileTree({
  dir,
  prefix,
  depth,
  open,
  toggle,
  openPath,
  onOpen,
}: {
  dir: Dir
  prefix: string
  depth: number
  open: Set<string>
  toggle: (key: string) => void
  openPath: string | null
  onOpen: (path: string) => void
}) {
  return (
    <>
      {[...dir.dirs.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, sub]) => {
          const key = `${prefix}/${name}`
          const isOpen = open.has(key)
          return (
            <li key={key}>
              <button type="button" className="tree-row dir" style={{ paddingLeft: 8 + depth * 14 }} onClick={() => toggle(key)} aria-expanded={isOpen}>
                <span className="caret">{isOpen ? '▾' : '▸'}</span> {name}
              </button>
              {isOpen && (
                <ul>
                  <FileTree dir={sub} prefix={key} depth={depth + 1} open={open} toggle={toggle} openPath={openPath} onOpen={onOpen} />
                </ul>
              )}
            </li>
          )
        })}
      {dir.files.map((f) => (
        <li key={f.path}>
          <button
            type="button"
            className={`tree-row file${openPath === f.path ? ' on' : ''}`}
            style={{ paddingLeft: 22 + depth * 14 }}
            onClick={() => onOpen(f.path)}
            title={f.path}
          >
            {f.rel.split('/').pop()}
          </button>
        </li>
      ))}
    </>
  )
}

function GrammarExplorer({
  selection,
  select,
  expanded,
  setExpanded,
}: {
  selection: Selection
  select: (s: Selection) => void
  expanded: Set<number>
  setExpanded: (f: (s: Set<number>) => Set<number>) => void
}) {
  const { status } = useApp()
  const [lists, setLists] = useState<Record<number, FileList>>({})
  const [openDirs, setOpenDirs] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const grammars = status?.grammars ?? []
  const openPath = selection?.kind === 'file' ? selection.path : null

  // load the file list of each expanded grammar once
  useEffect(() => {
    for (const id of expanded) {
      if (lists[id]) continue
      setLists((l) => ({ ...l, [id]: { status: 'loading' } }))
      api.grammarFiles(id).then(
        (r) => setLists((l) => ({ ...l, [id]: { status: 'done', files: r.files } })),
        (e) => setLists((l) => ({ ...l, [id]: { status: 'error', error: (e as Error).message } })),
      )
    }
  }, [expanded, lists])

  const toggleDir = (key: string) =>
    setOpenDirs((s) => {
      const next = new Set(s)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const toggleGrammar = (id: number) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const f = filter.trim().toLowerCase()
  return (
    <>
      <input placeholder="Filter files…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter files" />
      <ul className="explorer-tree" role="tree" aria-label="Grammars">
        {grammars.map((g) => {
          const isOpen = expanded.has(g.id)
          const list = lists[g.id]
          const active = status?.settings.activeGrammar === g.id
          const selected = selection?.kind === 'grammar' && selection.id === g.id
          return (
            <li key={g.id} role="treeitem" aria-expanded={isOpen} data-testid={`grammar-${g.id}`}>
              <div className={`tree-row grammar${selected ? ' on' : ''}`}>
                <button type="button" className="caret-btn" onClick={() => toggleGrammar(g.id)} aria-label={`${isOpen ? 'Collapse' : 'Expand'} ${g.name}`}>
                  {isOpen ? '▾' : '▸'}
                </button>
                <button type="button" className="grammar-name" onClick={() => select({ kind: 'grammar', id: g.id })}>
                  {g.name}
                </button>
                {active && <span className="badge active">active</span>}
                <CompileBadge g={g} />
              </div>
              {isOpen && (
                <ul>
                  {list?.status === 'loading' && <li className="muted small tree-note">Loading…</li>}
                  {list?.status === 'error' && <li className="error small tree-note">{list.error}</li>}
                  {list?.status === 'done' &&
                    (f ? (
                      list.files
                        .filter((x) => x.rel.toLowerCase().includes(f))
                        .map((x) => (
                          <li key={x.path}>
                            <button type="button" className={`tree-row file${openPath === x.path ? ' on' : ''}`} style={{ paddingLeft: 22 }} onClick={() => select({ kind: 'file', path: x.path })} title={x.path}>
                              {x.rel}
                            </button>
                          </li>
                        ))
                    ) : (
                      <FileTree
                        dir={buildTree(list.files)}
                        prefix={String(g.id)}
                        depth={1}
                        open={openDirs}
                        toggle={toggleDir}
                        openPath={openPath}
                        onOpen={(path) => select({ kind: 'file', path })}
                      />
                    ))}
                  {list?.status === 'done' && !list.files.length && <li className="muted small tree-note">No grammar files found.</li>}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}

/* ---- main pane: a grammar's details ---- */

function GrammarDetails({ g, onOpen }: { g: Grammar; onOpen: (path: string) => void }) {
  const { status, refresh, notify, setActiveGrammar } = useApp()
  const [log, setLog] = useState<string | null>(null)
  const active = status?.settings.activeGrammar === g.id
  const act = useAction(async (fn: () => Promise<unknown>) => {
    await fn()
    await refresh()
  })

  // the compile log, refreshed whenever the compile status changes
  useEffect(() => {
    if (g.kind !== 'source' || g.compileStatus === 'idle') {
      setLog(null)
      return
    }
    let stale = false
    api.grammar(g.id).then(
      (r) => !stale && setLog(r.grammar.compileLog ?? ''),
      () => {},
    )
    return () => {
      stale = true
    }
  }, [g.id, g.kind, g.compileStatus, g.compiledAt])

  return (
    <div className="card grammar-details" data-testid="grammar-details">
      <div className="row">
        <h2 className="grow">
          {g.name} {active && <span className="badge active">active</span>}
        </h2>
        <CompileBadge g={g} />
      </div>
      <dl className="kv">
        {g.configPath && (
          <>
            <dt>Config</dt>
            <dd>
              <button type="button" className="link" onClick={() => onOpen(g.configPath)}>
                <code>{g.configPath}</code>
              </button>
            </dd>
          </>
        )}
        <dt>Directory</dt>
        <dd>
          <code>{g.rootDir}</code>
        </dd>
        <dt>Image</dt>
        <dd>
          <code>{g.imagePath}</code>{' '}
          {g.image.exists ? (
            <span className="muted">
              {formatBytes(g.image.size)}, {new Date((g.image.mtime ?? 0) * 1000).toLocaleString()}
            </span>
          ) : (
            <span className="badge warn">missing</span>
          )}
        </dd>
      </dl>
      <div className="row wrap">
        {!active && (
          <button type="button" className="primary" onClick={() => act.run(() => setActiveGrammar(g.id))}>
            Use this grammar
          </button>
        )}
        {g.kind === 'source' && (
          <button
            type="button"
            disabled={g.compileStatus === 'running' || act.busy}
            onClick={() =>
              act.run(async () => {
                await api.compileGrammar(g.id)
                notify(`Compiling ${g.name}…`)
              })
            }
          >
            {g.image.exists ? 'Recompile' : 'Compile'}
          </button>
        )}
        <span className="grow" />
        <button
          type="button"
          className="danger"
          onClick={() => {
            if (window.confirm(`Remove "${g.name}" from IGDE? (No files are deleted.)`)) void act.run(() => api.removeGrammar(g.id))
          }}
        >
          Remove from IGDE
        </button>
      </div>
      {act.error && <div className="error">{act.error}</div>}
      {log !== null && (
        <>
          <h3 className="log-title">Compile log</h3>
          <pre className="code log" data-testid="compile-log">
            {log || '(empty)'}
          </pre>
        </>
      )}
    </div>
  )
}

/* ---- adding a grammar ---- */

function AddGrammar({ onClose, onAdded }: { onClose: () => void; onAdded: (g: Grammar) => void }) {
  const { refresh, notify } = useApp()
  const [compileNow, setCompileNow] = useState(true)
  const [manual, setManual] = useState('')
  const add = useAction(async (path: string) => {
    const info = await api.detectGrammar(path)
    const r = await api.addGrammar(
      info.kind === 'source'
        ? { configPath: info.configPath, name: info.name, compile: compileNow }
        : { imagePath: info.imagePath, name: info.name },
    )
    if (r.compileError) notify(r.compileError, 'error')
    else notify(`Added ${r.grammar.name}${info.kind === 'source' && compileNow ? '; compiling…' : ''}`, 'success')
    await refresh()
    onAdded(r.grammar)
  })
  const addable = (e: FsEntry) => e.hint === 'config' || e.hint === 'image' || e.hint === 'grammar-dir'
  return (
    <Modal title="Add a grammar" onClose={onClose}>
      <p className="muted">
        A grammar's ACE <code>config.tdl</code> (usually <code>&lt;grammar&gt;/ace/config.tdl</code>; IGDE compiles it with ACE), its folder,
        or an already compiled grammar image (<code>.dat</code>).
      </p>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault()
          if (manual.trim()) void add.run(manual.trim())
        }}
      >
        <input
          className="grow"
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          placeholder="/path/to/grammar/ace/config.tdl, a grammar folder, or a .dat image"
          aria-label="Grammar path"
          spellCheck={false}
        />
        <button type="submit" className="primary" disabled={add.busy || !manual.trim()}>
          Add
        </button>
      </form>
      <label className="row">
        <input type="checkbox" checked={compileNow} onChange={(e) => setCompileNow(e.target.checked)} /> Compile source grammars right away
      </label>
      {add.error && <div className="error">{add.error}</div>}
      <p className="muted">…or browse to it:</p>
      <FileBrowser
        entryActions={(e) =>
          addable(e) ? (
            <button type="button" className="small primary" disabled={add.busy} onClick={() => void add.run(e.path)}>
              Add
            </button>
          ) : null
        }
        dirActions={(l) =>
          l.hint === 'grammar-dir' ? (
            <button type="button" className="primary" disabled={add.busy} onClick={() => void add.run(l.path)}>
              Add this grammar
            </button>
          ) : null
        }
      />
    </Modal>
  )
}

/* ---- the page ---- */

export function GrammarsPage() {
  const { status, refresh, notify, takeIntent } = useApp()
  const [selection, setSelection] = useState<Selection>(null)
  const [tab, setTab] = useState<'grammars' | 'disk'>('grammars')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [adding, setAdding] = useState(false)
  const [changed, setChanged] = useState<Set<number>>(new Set()) // grammars with unrecompiled edits
  const grammars = useMemo(() => status?.grammars ?? [], [status])

  const select = useCallback(
    (s: Selection) => {
      setSelection(s)
      // reveal an opened file under its grammar
      if (s?.kind === 'file') {
        const g = owningGrammar(grammars, s.path)
        if (g) setExpanded((e) => (e.has(g.id) ? e : new Set(e).add(g.id)))
      }
    },
    [grammars],
  )

  // "open this file at this line" from elsewhere (e.g. a TDL definition)
  useEffect(() => {
    const i = takeIntent('grammars')
    if (i) select({ kind: 'file', path: i.path, line: i.line })
  }, [takeIntent, select])

  // forget a grammar that was removed
  useEffect(() => {
    if (selection?.kind === 'grammar' && status && !grammars.some((g) => g.id === selection.id)) setSelection(null)
  }, [selection, grammars, status])

  // show the active grammar until something else is chosen
  useEffect(() => {
    const active = status?.activeGrammar
    // functional update: don't clobber a file opened in this same render
    if (!selection && active) setSelection((s) => s ?? { kind: 'grammar', id: active.id })
  }, [selection, status])

  // poll while a grammar compiles
  const running = grammars.some((g) => g.compileStatus === 'running')
  useEffect(() => {
    if (!running) return
    const t = window.setInterval(() => void refresh(), 1000)
    return () => window.clearInterval(t)
  }, [running, refresh])

  const selectedGrammar = selection?.kind === 'grammar' ? grammars.find((g) => g.id === selection.id) : undefined
  const fileGrammar = selection?.kind === 'file' ? owningGrammar(grammars, selection.path) : undefined

  const onSaved = useCallback(
    (path: string) => {
      notify(`Saved ${path.split('/').pop()}`, 'success')
      const g = owningGrammar(grammars, path)
      if (g?.kind === 'source') setChanged((s) => new Set(s).add(g.id))
    },
    [grammars, notify],
  )

  const recompile = async (g: Grammar) => {
    try {
      await api.compileGrammar(g.id)
      setChanged((s) => {
        const next = new Set(s)
        next.delete(g.id)
        return next
      })
      notify(`Compiling ${g.name}…`)
      await refresh()
    } catch (e) {
      notify((e as Error).message, 'error')
    }
  }

  if (!status) return <div className="page">Loading…</div>

  return (
    <div className="page grammars-page">
      <aside className="explorer card">
        <div className="row">
          <div className="segmented grow" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'grammars'} className={tab === 'grammars' ? 'on' : ''} onClick={() => setTab('grammars')}>
              Grammars
            </button>
            <button type="button" role="tab" aria-selected={tab === 'disk'} className={tab === 'disk' ? 'on' : ''} onClick={() => setTab('disk')}>
              Disk
            </button>
          </div>
          <button type="button" className="primary small" onClick={() => setAdding(true)} title="Add a grammar">
            + Add grammar
          </button>
        </div>
        {tab === 'grammars' &&
          (grammars.length ? (
            <GrammarExplorer selection={selection} select={select} expanded={expanded} setExpanded={setExpanded} />
          ) : (
            <div className="empty small">No grammars yet.</div>
          ))}
        {tab === 'disk' && (
          <FileBrowser
            initialPath={selection?.kind === 'file' ? dirname(selection.path) : undefined}
            selectedPath={selection?.kind === 'file' ? selection.path : null}
            onOpenFile={(e) => select({ kind: 'file', path: e.path })}
          />
        )}
      </aside>

      <section className="grammars-main">
        {selection?.kind === 'file' && (
          <>
            {fileGrammar && (
              <div className={`file-context${changed.has(fileGrammar.id) ? ' changed' : ''}`}>
                <span>
                  In grammar{' '}
                  <button type="button" className="link" onClick={() => select({ kind: 'grammar', id: fileGrammar.id })}>
                    {fileGrammar.name}
                  </button>
                  {changed.has(fileGrammar.id) && <> · sources changed since the last compile</>}
                </span>
                <span className="grow" />
                {fileGrammar.kind === 'source' && (
                  <button
                    type="button"
                    className={changed.has(fileGrammar.id) ? 'primary small' : 'small'}
                    disabled={fileGrammar.compileStatus === 'running'}
                    onClick={() => void recompile(fileGrammar)}
                  >
                    {fileGrammar.compileStatus === 'running' ? 'Compiling…' : `Recompile ${fileGrammar.name}`}
                  </button>
                )}
              </div>
            )}
            <FileEditor key={`${selection.path}:${selection.line ?? ''}`} path={selection.path} line={selection.line} onSaved={onSaved} />
          </>
        )}
        {selectedGrammar && <GrammarDetails g={selectedGrammar} onOpen={(path) => select({ kind: 'file', path })} />}
        {!selection && (
          <div className="empty">
            {grammars.length ? (
              'Select a grammar or open one of its files.'
            ) : (
              <>
                Point IGDE at a grammar stored on this machine.{' '}
                <button type="button" className="primary" onClick={() => setAdding(true)}>
                  Add a grammar
                </button>
              </>
            )}
          </div>
        )}
      </section>

      {adding && (
        <AddGrammar
          onClose={() => setAdding(false)}
          onAdded={(g) => {
            setAdding(false)
            setTab('grammars')
            setSelection({ kind: 'grammar', id: g.id })
            setExpanded((e) => new Set(e).add(g.id))
          }}
        />
      )}
    </div>
  )
}
