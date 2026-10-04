import { useEffect, useState } from 'react'
import { api } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { Modal } from '../components/Modal'
import { useAction, useApp } from '../state'
import type { FsEntry, Grammar } from '../types'

function formatBytes(n: number | null) {
  if (n === null) return ''
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${(n / 1024).toFixed(1)} KB`
}

function CompileBadge({ g }: { g: Grammar }) {
  if (g.kind === 'image') return <span className="badge">precompiled image</span>
  const label = { idle: 'not compiled', running: 'compiling…', ok: 'compiled', failed: 'compile failed' }[g.compileStatus]
  return <span className={`badge compile-${g.compileStatus}`}>{label}</span>
}

function GrammarCard({ g, active }: { g: Grammar; active: boolean }) {
  const { refresh, notify, navigate, setActiveGrammar } = useApp()
  const [log, setLog] = useState<string | null>(null)
  const act = useAction(async (fn: () => Promise<unknown>) => {
    await fn()
    await refresh()
  })
  return (
    <div className={`card grammar-card${active ? ' active' : ''}`} data-testid={`grammar-${g.id}`}>
      <div className="row">
        <h3 className="grow">
          {g.name} {active && <span className="badge active">active</span>}
        </h3>
        <CompileBadge g={g} />
      </div>
      <dl className="kv">
        {g.configPath && (
          <>
            <dt>Config</dt>
            <dd>
              <code>{g.configPath}</code>
            </dd>
          </>
        )}
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
        {g.kind === 'source' && g.compileStatus !== 'idle' && (
          <button type="button" onClick={async () => setLog((await api.grammar(g.id)).grammar.compileLog ?? '')}>
            Compile log
          </button>
        )}
        <button type="button" onClick={() => navigate('files', { page: 'files', path: g.configPath || g.rootDir })}>
          Files
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => {
            if (window.confirm(`Remove "${g.name}" from IGDE? (No files are deleted.)`)) void act.run(() => api.removeGrammar(g.id))
          }}
        >
          Remove
        </button>
      </div>
      {act.error && <div className="error">{act.error}</div>}
      {log !== null && (
        <Modal title={`Compile log: ${g.name}`} onClose={() => setLog(null)}>
          <pre className="code log">{log || '(empty)'}</pre>
        </Modal>
      )}
    </div>
  )
}

export function GrammarsPage() {
  const { status, refresh, notify } = useApp()
  const [adding, setAdding] = useState(false)
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
    setAdding(false)
    setManual('')
    await refresh()
  })

  // Poll while a compile is running.
  const running = status?.grammars.some((g) => g.compileStatus === 'running')
  useEffect(() => {
    if (!running) return
    const t = window.setInterval(() => void refresh(), 1000)
    return () => window.clearInterval(t)
  }, [running, refresh])

  if (!status) return <div className="page">Loading…</div>
  const addable = (e: FsEntry) => e.hint === 'config' || e.hint === 'image' || e.hint === 'grammar-dir'

  return (
    <div className="page">
      <div className="row">
        <h2 className="grow">Grammars</h2>
        <button type="button" className="primary" onClick={() => setAdding(true)}>
          Add grammar…
        </button>
      </div>
      <p className="muted">
        Point IGDE at grammars stored on this machine: a grammar's ACE <code>config.tdl</code> (usually{' '}
        <code>&lt;grammar&gt;/ace/config.tdl</code>; IGDE compiles it with ACE) or an already compiled grammar image
        (<code>.dat</code>).
      </p>
      {!status.grammars.length && <div className="empty">No grammars yet. Click “Add grammar…” to choose one.</div>}
      <div className="grammar-list">
        {status.grammars.map((g) => (
          <GrammarCard key={g.id} g={g} active={status.settings.activeGrammar === g.id} />
        ))}
      </div>
      {adding && (
        <Modal title="Add a grammar" onClose={() => setAdding(false)}>
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
            <input type="checkbox" checked={compileNow} onChange={(e) => setCompileNow(e.target.checked)} /> Compile
            source grammars right away
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
      )}
    </div>
  )
}
