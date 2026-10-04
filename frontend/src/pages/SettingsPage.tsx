import { useEffect, useState } from 'react'
import { api } from '../api'
import { FileBrowser } from '../components/FileBrowser'
import { Modal } from '../components/Modal'
import { useAction, useApp } from '../state'
import type { AceStatus, Settings } from '../types'

const SOURCE_LABEL = {
  settings: 'ACE_ROOT',
  env: 'the $ACE_ROOT environment variable',
  path: '$PATH',
  homebrew: 'Homebrew',
}

const BREW_INSTALL = 'brew install delph-in/delphin/ace'

function DetectedAce({ onUse }: { onUse: (path: string) => void }) {
  const [found, setFound] = useState<Awaited<ReturnType<typeof api.detectAce>>['found'] | null>(null)
  useEffect(() => {
    api.detectAce().then((r) => setFound(r.found), () => setFound([]))
  }, [])
  if (found === null) return null
  return (
    <div className="detected">
      {found.length > 0 ? (
        <>
          <div className="muted small">ACE installations found on this machine:</div>
          <ul>
            {found.map((f) => (
              <li key={f.path}>
                <code>{f.path}</code> <span className="badge">ACE {f.version}</span>{' '}
                <span className="muted small">({SOURCE_LABEL[f.source]})</span>{' '}
                <button type="button" className="small" onClick={() => onUse(f.path)}>
                  Use
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted small">No ACE installation found on $PATH or in Homebrew.</p>
      )}
      <p className="muted small">
        To install ACE with <a href="https://brew.sh">Homebrew</a> (macOS or Linux): <code>{BREW_INSTALL}</code>{' '}
        <button type="button" className="small ghost" onClick={() => void navigator.clipboard?.writeText(BREW_INSTALL)}>
          Copy
        </button>
      </p>
    </div>
  )
}

function AceStatusCard({ ace }: { ace: AceStatus }) {
  return (
    <div className={`status-card ${ace.ok ? 'ok' : 'bad'}`} data-testid="ace-status">
      <div className="status-title">{ace.ok ? `ACE ${ace.version}` : 'ACE not available'}</div>
      {ace.executable && (
        <div>
          Executable: <code>{ace.executable}</code>
        </div>
      )}
      {ace.source && (
        <div className="muted">
          Found via {SOURCE_LABEL[ace.source]}
        </div>
      )}
      {ace.error && <div className="error">{ace.error}</div>}
    </div>
  )
}

const LIMITS: { key: keyof Settings; label: string; help: string; min: number }[] = [
  { key: 'maxResults', label: 'Results per item', help: 'ACE -n: how many parses/realizations to unpack', min: 1 },
  { key: 'timeoutSeconds', label: 'Timeout (seconds)', help: 'ACE --timeout', min: 1 },
  { key: 'maxChartMegabytes', label: 'Chart memory (MB)', help: 'ACE --max-chart-megabytes', min: 10 },
  { key: 'maxUnpackMegabytes', label: 'Unpacking memory (MB)', help: 'ACE --max-unpack-megabytes', min: 10 },
]

export function SettingsPage() {
  const { status, refresh, notify } = useApp()
  const [form, setForm] = useState<Settings | null>(null)
  const [test, setTest] = useState<AceStatus | null>(null)
  const [picker, setPicker] = useState<null | 'aceRoot' | 'grammarImageDir' | 'profilesDir'>(null)
  const save = useAction(api.saveSettings)
  const tester = useAction(api.testAce)
  const stopper = useAction(api.stopProcess)

  useEffect(() => {
    if (status && !form) setForm(status.settings)
  }, [status, form])

  if (!status || !form) return <div className="page">Loading…</div>

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setForm({ ...form, [k]: v })

  const onSave = async () => {
    const r = await save.run(form)
    if (r) {
      setForm(r.settings)
      setTest(null)
      notify(r.ace.ok ? `Using ACE ${r.ace.version}` : 'Settings saved', 'success')
      await refresh()
    }
  }

  return (
    <div className="page settings-page">
      <section className="card">
        <h2>ACE</h2>
        <p className="muted">
          IGDE drives a local install of the <a href="https://sweaglesw.org/linguistics/ace/">ACE</a> parser/generator. Point
          ACE_ROOT at the directory containing the <code>ace</code> binary (for example an unpacked{' '}
          <code>ace-0.9.34</code> release or a Homebrew prefix) or at the binary itself. Leave it empty to use{' '}
          <code>$ACE_ROOT</code>, <code>ace</code> on <code>$PATH</code>, or a Homebrew install.
        </p>
        <AceStatusCard ace={status.ace} />
        <DetectedAce onUse={(path) => set('aceRoot', path)} />
        <label className="field">
          <span>ACE_ROOT</span>
          <div className="row">
            <input
              value={form.aceRoot}
              onChange={(e) => set('aceRoot', e.target.value)}
              placeholder={status.envAceRoot ? `$ACE_ROOT (${status.envAceRoot})` : 'empty: find ACE automatically ($PATH, Homebrew)'}
              spellCheck={false}
              aria-label="ACE_ROOT"
            />
            <button type="button" onClick={() => setPicker('aceRoot')}>
              Browse…
            </button>
            <button
              type="button"
              disabled={tester.busy}
              onClick={async () => setTest((await tester.run(form.aceRoot)) ?? null)}
            >
              Test
            </button>
          </div>
        </label>
        {test && <AceStatusCard ace={test} />}
        {tester.error && <div className="error">{tester.error}</div>}

        <h3>Processing limits</h3>
        <div className="grid-fields">
          {LIMITS.map((l) => (
            <label className="field" key={l.key}>
              <span>{l.label}</span>
              <input
                type="number"
                min={l.min}
                value={form[l.key] as number}
                onChange={(e) => set(l.key, Number(e.target.value) as never)}
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
          <small className="muted">Where grammars compiled from a config.tdl are written.</small>
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
          <h2 className="grow">ACE processes</h2>
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
          <p className="muted">No ACE processes running.</p>
        )}
        <p className="muted small">
          IGDE data directory: <code>{status.igdeHome}</code>
        </p>
      </section>

      {picker && (
        <Modal title={picker === 'aceRoot' ? 'Choose ACE_ROOT' : picker === 'profilesDir' ? 'Choose test suite runs directory' : 'Choose compiled grammar directory'} onClose={() => setPicker(null)}>
          <FileBrowser
            mode={picker === 'aceRoot' ? 'pick-file' : 'pick-dir'}
            accept={(e) => e.name === 'ace'}
            onPick={(path) => {
              set(picker, path)
              setPicker(null)
            }}
            dirActions={
              picker === 'aceRoot'
                ? (l) => (
                    <button
                      type="button"
                      className="primary"
                      onClick={() => {
                        set('aceRoot', l.path)
                        setPicker(null)
                      }}
                    >
                      Use this folder as ACE_ROOT
                    </button>
                  )
                : undefined
            }
          />
          {picker === 'aceRoot' && <p className="muted">Pick the folder containing <code>ace</code>, or click the <code>ace</code> binary.</p>}
        </Modal>
      )}
    </div>
  )
}
