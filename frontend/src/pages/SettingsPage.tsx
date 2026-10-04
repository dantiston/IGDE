import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ProcessorInput } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { Modal } from '../components/Modal'
import { useAction, useApp } from '../state'
import type { Backend, Install, Processor, ProcessorStatus, Settings } from '../types'

const CAPABILITY_LABEL: Record<string, string> = {
  parse: 'parsing',
  generate: 'generation',
  tfs: 'TFS browsing (LUI)',
  compile: 'grammar compilation',
}

function StatusCard({ status, backend, testId }: { status: ProcessorStatus; backend?: Backend; testId?: string }) {
  const label = backend?.label ?? 'Processor'
  return (
    <div className={`status-card ${status.ok ? 'ok' : 'bad'}`} data-testid={testId}>
      <div className="status-title">{status.ok ? `${label} ${status.version}` : `${label} not available`}</div>
      {status.executable && (
        <div>
          Executable: <code>{status.executable}</code>
        </div>
      )}
      {status.source && <div className="muted">Found via {backend?.sources[status.source] ?? status.source}</div>}
      {status.error && <div className="error">{status.error}</div>}
    </div>
  )
}

function Detected({
  backend,
  found,
  onUse,
}: {
  backend: Backend
  found: Install[] | null
  onUse: (path: string) => void
}) {
  if (found === null) return null
  const mine = found.filter((f) => f.backend === backend.key)
  return (
    <div className="detected">
      {mine.length > 0 ? (
        <>
          <div className="muted small">{backend.label} installations found on this machine:</div>
          <ul>
            {mine.map((f) => (
              <li key={f.path}>
                <code>{f.path}</code>{' '}
                <span className="badge">
                  {backend.label} {f.version}
                </span>{' '}
                <span className="muted small">({backend.sources[f.source] ?? f.source})</span>{' '}
                <button type="button" className="small" onClick={() => onUse(f.path)}>
                  Use
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted small">No {backend.label} installation found on this machine.</p>
      )}
      {backend.installCommand && (
        <p className="muted small">
          To install {backend.label}: <code>{backend.installCommand}</code>{' '}
          <button
            type="button"
            className="small ghost"
            onClick={() => void navigator.clipboard?.writeText(backend.installCommand)}
          >
            Copy
          </button>
        </p>
      )}
    </div>
  )
}

interface FormValues {
  name: string
  location: string
  options: Record<string, number | string>
}

/** Name, location and backend options of a processor. */
function ProcessorForm({
  backend,
  initial,
  found,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  backend: Backend
  initial: FormValues
  found: Install[] | null
  submitLabel: string
  onSubmit: (v: ProcessorInput) => Promise<boolean>
  onCancel?: () => void
}) {
  const [form, setForm] = useState(initial)
  const [test, setTest] = useState<ProcessorStatus | null>(null)
  const [picker, setPicker] = useState(false)
  const tester = useAction(api.checkProcessor)
  const submit = useAction(onSubmit)
  const setLocation = (location: string) => {
    setForm((f) => ({ ...f, location }))
    setTest(null)
  }
  const envHint = Object.entries(backend.envVars)
    .filter(([, v]) => v)
    .map(([k, v]) => `$${k} (${v})`)
    .join(', ')

  return (
    <>
      <form
        className="processor-form"
        onSubmit={async (e) => {
          e.preventDefault()
          await submit.run({ name: form.name, location: form.location, options: form.options })
        }}
      >
        <label className="field">
          <span>Name</span>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            aria-label="Processor name"
          />
        </label>
        <p className="muted small">{backend.locationHelp}</p>
        <Detected backend={backend} found={found} onUse={setLocation} />
        <label className="field">
          <span>{backend.locationLabel}</span>
          <div className="row">
            <input
              value={form.location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder={envHint ? `empty: ${envHint}` : `empty: find ${backend.label} automatically`}
              spellCheck={false}
              aria-label={backend.locationLabel}
            />
            <button type="button" onClick={() => setPicker(true)}>
              Browse…
            </button>
            <button
              type="button"
              disabled={tester.busy}
              onClick={async () => setTest((await tester.run(backend.key, form.location)) ?? null)}
            >
              Test
            </button>
          </div>
        </label>
        {test && <StatusCard status={test} backend={backend} testId="processor-test" />}
        {tester.error && <div className="error">{tester.error}</div>}
        {backend.options.length > 0 && (
          <div className="grid-fields">
            {backend.options.map((o) => (
              <label className="field" key={o.key}>
                <span>{o.label}</span>
                <input
                  type={o.type === 'int' ? 'number' : 'text'}
                  min={o.min ?? undefined}
                  max={o.max ?? undefined}
                  value={form.options[o.key] ?? o.default}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      options: { ...form.options, [o.key]: o.type === 'int' ? Number(e.target.value) : e.target.value },
                    })
                  }
                />
                <small className="muted">{o.help}</small>
              </label>
            ))}
          </div>
        )}
        <div className="row end">
          {submit.error && <div className="error grow">{submit.error}</div>}
          {onCancel && (
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
          )}
          <button type="submit" className="primary" disabled={submit.busy}>
            {submit.busy ? 'Saving…' : submitLabel}
          </button>
        </div>
      </form>
      {picker && (
        <Modal title={`Choose ${backend.locationLabel}`} onClose={() => setPicker(false)}>
          <FileBrowser
            mode="pick-file"
            onPick={(path) => {
              setLocation(path)
              setPicker(false)
            }}
            dirActions={(l) => (
              <button
                type="button"
                className="primary"
                onClick={() => {
                  setLocation(l.path)
                  setPicker(false)
                }}
              >
                Use this folder
              </button>
            )}
          />
          <p className="muted">Pick the {backend.label} executable, or the folder containing it.</p>
        </Modal>
      )}
    </>
  )
}

function ProcessorCard({ p, backend, found }: { p: Processor; backend?: Backend; found: Install[] | null }) {
  const { refresh, notify } = useApp()
  const [editing, setEditing] = useState(false)
  const action = useAction(async (fn: () => Promise<unknown>) => {
    await fn()
    await refresh()
  })
  return (
    <div className="processor-card" data-testid="processor">
      <div className="row">
        <h3 className="grow">
          {p.name} {p.name !== p.backendLabel && <span className="badge">{p.backendLabel}</span>}
          {p.isDefault && <span className="badge active">default</span>}
        </h3>
        {!editing && backend && (
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
        {!p.isDefault && (
          <button
            type="button"
            disabled={action.busy}
            onClick={() => void action.run(() => api.saveSettings({ defaultProcessor: p.id }))}
          >
            Make default
          </button>
        )}
        <button
          type="button"
          className="danger"
          disabled={action.busy}
          onClick={() => {
            const uses = p.grammars
              ? ` ${p.grammars} grammar(s) use it and will use the default processor instead.`
              : ''
            if (window.confirm(`Remove the processor “${p.name}”? Nothing is deleted from disk.${uses}`))
              void action.run(() => api.removeProcessor(p.id))
          }}
        >
          Remove
        </button>
      </div>
      <StatusCard status={p.status} backend={backend} testId="processor-status" />
      {backend && (
        <div className="muted small">
          {p.location ? (
            <>
              {backend.locationLabel}: <code>{p.location}</code>
            </>
          ) : (
            `${backend.locationLabel} not set: found automatically`
          )}
          {backend.options.map((o) => (
            <span key={o.key}>
              {' · '}
              {o.label}: {p.options[o.key]}
            </span>
          ))}
          {' · '}
          {backend.capabilities.map((c) => CAPABILITY_LABEL[c] ?? c).join(', ')}
        </div>
      )}
      {action.error && <div className="error">{action.error}</div>}
      {editing && backend && (
        <ProcessorForm
          backend={backend}
          initial={{ name: p.name, location: p.location, options: p.options }}
          found={found}
          submitLabel="Save processor"
          onCancel={() => setEditing(false)}
          onSubmit={async (v) => {
            const r = await api.updateProcessor(p.id, v)
            setEditing(false)
            notify(
              r.processor.status.ok
                ? `${r.processor.name}: ${backend.label} ${r.processor.status.version}`
                : 'Processor saved',
              'success',
            )
            await refresh()
            return true
          }}
        />
      )}
    </div>
  )
}

function AddProcessor({
  backends,
  found,
  onDone,
}: {
  backends: Backend[]
  found: Install[] | null
  onDone: () => void
}) {
  const { refresh, notify } = useApp()
  const [key, setKey] = useState(backends[0]?.key ?? '')
  const backend = backends.find((b) => b.key === key)
  return (
    <div className="processor-card" data-testid="add-processor">
      <h3>Add a processor</h3>
      <label className="field">
        <span>Type</span>
        <select value={key} onChange={(e) => setKey(e.target.value)} aria-label="Processor type">
          {backends.map((b) => (
            <option key={b.key} value={b.key}>
              {b.label}
            </option>
          ))}
        </select>
      </label>
      {backend && (
        <>
          <p className="muted small">
            {backend.description}{' '}
            {backend.homepage && (
              <a href={backend.homepage} target="_blank" rel="noreferrer">
                {backend.homepage}
              </a>
            )}
          </p>
          <ProcessorForm
            key={backend.key}
            backend={backend}
            initial={{ name: backend.label, location: '', options: {} }}
            found={found}
            submitLabel="Add processor"
            onCancel={onDone}
            onSubmit={async (v) => {
              const r = await api.addProcessor({ ...v, backend: backend.key })
              notify(`Added ${r.processor.name}`, 'success')
              await refresh()
              onDone()
              return true
            }}
          />
        </>
      )}
    </div>
  )
}

const LIMITS: { key: 'maxResults' | 'timeoutSeconds'; label: string; help: string; min: number }[] = [
  { key: 'maxResults', label: 'Results per input', help: 'How many parses or realizations to keep', min: 1 },
  { key: 'timeoutSeconds', label: 'Timeout (seconds)', help: 'Time allowed for one input', min: 1 },
]

export function SettingsPage() {
  const { status, refresh, notify } = useApp()
  const [form, setForm] = useState<Settings | null>(null)
  const [picker, setPicker] = useState<null | 'grammarImageDir' | 'profilesDir'>(null)
  const [adding, setAdding] = useState(false)
  const [found, setFound] = useState<Install[] | null>(null)
  const save = useAction(api.saveSettings)
  const stopper = useAction(api.stopProcess)

  useEffect(() => {
    if (status && !form) setForm(status.settings)
  }, [status, form])
  useEffect(() => {
    api.detectProcessors().then(
      (r) => setFound(r.found),
      () => setFound([]),
    )
    void refresh() // e.g. the processes started since the status was loaded
  }, [refresh])

  if (!status || !form) return <div className="page">Loading…</div>

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setForm({ ...form, [k]: v })
  const backendOf = (key: string) => status.backends.find((b) => b.key === key)

  const onSave = async () => {
    const r = await save.run({
      maxResults: form.maxResults,
      timeoutSeconds: form.timeoutSeconds,
      grammarImageDir: form.grammarImageDir,
      profilesDir: form.profilesDir,
    })
    if (r) {
      setForm(r.settings)
      notify('Settings saved', 'success')
      await refresh()
    }
  }

  return (
    <div className="page settings-page">
      <section className="card" data-testid="processors">
        <div className="row">
          <h2 className="grow">Processors</h2>
          {!adding && (
            <button type="button" onClick={() => setAdding(true)}>
              + Add processor
            </button>
          )}
        </div>
        <p className="muted">
          IGDE parses, generates and browses feature structures by driving a grammar processor installed on this machine
          (types: {status.backends.map((b) => b.label).join(', ')}). Each grammar runs with the default processor unless
          you choose another one for it in Grammars.
        </p>
        {adding && <AddProcessor backends={status.backends} found={found} onDone={() => setAdding(false)} />}
        {status.processors.map((p) => (
          <ProcessorCard key={p.id} p={p} backend={backendOf(p.backend)} found={found} />
        ))}
        {!status.processors.length && !adding && <p className="muted">No processors configured yet.</p>}
      </section>

      <section className="card">
        <h2>Processing</h2>
        <div className="grid-fields">
          {LIMITS.map((l) => (
            <label className="field" key={l.key}>
              <span>{l.label}</span>
              <input
                type="number"
                min={l.min}
                value={form[l.key]}
                onChange={(e) => set(l.key, Number(e.target.value))}
              />
              <small className="muted">{l.help}</small>
            </label>
          ))}
        </div>
        <label className="field">
          <span>Compiled grammar directory</span>
          <div className="row">
            <input
              value={form.grammarImageDir}
              placeholder={form.defaultGrammarImageDir}
              onChange={(e) => set('grammarImageDir', e.target.value)}
              spellCheck={false}
            />
            <button type="button" onClick={() => setPicker('grammarImageDir')}>
              Browse…
            </button>
          </div>
          <small className="muted">Where grammars compiled from their configuration file are written.</small>
        </label>
        <label className="field">
          <span>Test suite runs directory</span>
          <div className="row">
            <input
              value={form.profilesDir}
              placeholder={form.defaultProfilesDir}
              onChange={(e) => set('profilesDir', e.target.value)}
              spellCheck={false}
              aria-label="Test suite runs directory"
            />
            <button type="button" onClick={() => setPicker('profilesDir')}>
              Browse…
            </button>
          </div>
          <small className="muted">Where the [incr tsdb()] profiles of test suite runs are written.</small>
        </label>
        <div className="row end">
          {save.error && <div className="error grow">{save.error}</div>}
          <button type="button" className="primary" disabled={save.busy} onClick={onSave}>
            {save.busy ? 'Saving…' : 'Save settings'}
          </button>
        </div>
      </section>

      <section className="card">
        <div className="row">
          <h2 className="grow">Running processes</h2>
          <button type="button" onClick={() => void refresh()}>
            Refresh
          </button>
          <button
            type="button"
            disabled={!status.processes.length || stopper.busy}
            onClick={async () => {
              await stopper.run(undefined)
              await refresh()
            }}
          >
            Stop all
          </button>
        </div>
        <p className="muted">
          IGDE keeps one parser, one generator and one TFS-browsing (LUI) session per grammar running; they restart
          automatically when needed.
        </p>
        {status.processes.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>Grammar</th>
                <th>Processor</th>
                <th>PID</th>
                <th>Requests</th>
                <th>Started</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {status.processes.map((p) => (
                <tr key={p.key}>
                  <td>{p.kind === 'lui' ? 'TFS (LUI)' : p.kind}</td>
                  <td>{p.grammarName}</td>
                  <td>{p.processorName}</td>
                  <td>{p.pid}</td>
                  <td>{p.requests}</td>
                  <td>{new Date(p.started * 1000).toLocaleTimeString()}</td>
                  <td>
                    <button
                      type="button"
                      onClick={async () => {
                        await stopper.run(p.key)
                        await refresh()
                      }}
                    >
                      Stop
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">No processes running.</p>
        )}
        <p className="muted small">
          IGDE data directory: <code>{status.igdeHome}</code>
        </p>
      </section>

      {picker && (
        <Modal
          title={picker === 'profilesDir' ? 'Choose test suite runs directory' : 'Choose compiled grammar directory'}
          onClose={() => setPicker(null)}
        >
          <FileBrowser
            mode="pick-dir"
            onPick={(path) => {
              set(picker, path)
              setPicker(null)
            }}
          />
        </Modal>
      )}
    </div>
  )
}
