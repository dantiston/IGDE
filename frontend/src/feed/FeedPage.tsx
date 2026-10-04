import { useEffect, useMemo, useRef, useState } from 'react'
import { GrammarRequired, useHistory } from '../pages/common'
import { useApp } from '../state'
import { KIND_LABEL, useFeed } from './FeedContext'
import type { LookupKind } from './FeedContext'
import { FeedItemView } from './FeedItems'

type Mode = 'parse' | 'generate' | 'lookup'

const looksLikeMrs = (s: string) => /^\s*\[/.test(s) && /RELS:/.test(s)

function Composer() {
  const { status } = useApp()
  const feed = useFeed()
  const [mode, setMode] = useState<Mode>('parse')
  const [sentence, setSentence] = useState('')
  const [mrs, setMrs] = useState('')
  const [mrsOrigin, setMrsOrigin] = useState('pasted MRS')
  const [n, setN] = useState('')
  const [kind, setKind] = useState<LookupKind>('type')
  const [name, setName] = useState('')
  const history = useHistory('igde.parse.history')
  const nValue = n ? Number(n) : undefined

  // MRSs of parse results already in the feed, to generate from
  const feedMrss = useMemo(
    () =>
      feed.items.flatMap((it) =>
        it.kind === 'parse' && it.state.status === 'done'
          ? it.state.data.results
              .filter((r) => r.simplemrs || r.mrsString)
              .map((r, i) => ({ key: `${it.id}:${i}`, label: `“${it.sentence}” #${i + 1}`, mrs: r.simplemrs ?? r.mrsString ?? '' }))
          : [],
      ),
    [feed.items],
  )

  const submitParse = () => {
    const s = sentence.trim()
    if (!s) return
    history.add(s)
    feed.parse(s, nValue)
    setSentence('')
  }
  const submitGenerate = () => {
    if (!mrs.trim()) return
    feed.generate(mrs, mrsOrigin, nValue)
  }

  const nInput = (
    <input
      className="n-input"
      type="number"
      min={1}
      value={n}
      onChange={(e) => setN(e.target.value)}
      placeholder={String(status?.settings.maxResults ?? 5)}
      aria-label="Maximum results"
      title="Maximum number of results per input"
    />
  )

  return (
    <div className="composer card">
      <div className="segmented" role="tablist" aria-label="What to do">
        {(['parse', 'generate', 'lookup'] as Mode[]).map((m) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>
            {m === 'parse' ? 'Parse' : m === 'generate' ? 'Generate' : 'Look up'}
          </button>
        ))}
      </div>
      {mode === 'parse' && (
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault()
            submitParse()
          }}
        >
          <input
            className="sentence grow"
            value={sentence}
            onChange={(e) => setSentence(e.target.value)}
            onPaste={(e) => {
              const text = e.clipboardData.getData('text')
              if (looksLikeMrs(text)) {
                e.preventDefault()
                setMrs(text)
                setMrsOrigin('pasted MRS')
                setMode('generate')
              }
            }}
            placeholder="Type a sentence and press Enter (or paste an MRS to generate from it)"
            aria-label="Sentence"
            list="parse-history"
            autoFocus
          />
          <datalist id="parse-history">
            {history.items.map((h) => (
              <option key={h} value={h} />
            ))}
          </datalist>
          {nInput}
          <button type="submit" className="primary" disabled={!sentence.trim()}>
            Parse
          </button>
        </form>
      )}
      {mode === 'generate' && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submitGenerate()
          }}
        >
          <textarea
            className="mrs-input"
            value={mrs}
            onChange={(e) => {
              setMrs(e.target.value)
              setMrsOrigin('pasted MRS')
            }}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault()
                submitGenerate()
              }
            }}
            placeholder="Paste an MRS (SimpleMRS), or pick one from a parse in the feed"
            aria-label="MRS to generate from"
            spellCheck={false}
            rows={5}
          />
          <div className="row">
            <select
              aria-label="MRS from the feed"
              value=""
              disabled={!feedMrss.length}
              onChange={(e) => {
                const m = feedMrss.find((x) => x.key === e.target.value)
                if (m) {
                  setMrs(m.mrs)
                  setMrsOrigin(m.label)
                }
              }}
            >
              <option value="">{feedMrss.length ? 'Use an MRS from the feed…' : 'No parses in the feed yet'}</option>
              {feedMrss.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
            <span className="grow muted small">{mrsOrigin !== 'pasted MRS' && `MRS of ${mrsOrigin}`}</span>
            {nInput}
            <button type="submit" className="primary" disabled={!mrs.trim()}>
              Generate
            </button>
          </div>
        </form>
      )}
      {mode === 'lookup' && (
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault()
            void feed.lookup(kind, name)
          }}
        >
          <select value={kind} onChange={(e) => setKind(e.target.value as LookupKind)} aria-label="What to look up">
            {(Object.keys(KIND_LABEL) as LookupKind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </select>
          <input className="grow" value={name} onChange={(e) => setName(e.target.value)} placeholder="name (or part of one)" aria-label="Name to look up" spellCheck={false} />
          <button type="submit" className="primary" disabled={!name.trim()}>
            Show
          </button>
          {kind === 'type' && (
            <button type="button" disabled={!name.trim()} onClick={() => feed.hierarchy(name)}>
              Hierarchy
            </button>
          )}
        </form>
      )}
    </div>
  )
}

function UnifyBar() {
  const { items, unifySource, unifyTarget, unify, clearUnify } = useFeed()
  if (!unifySource) return null
  const title = (id: number) => {
    const it = items.find((x) => x.id === id)
    return it?.kind === 'avm' ? it.title : '?'
  }
  return (
    <div className="unify-bar card active" role="status">
      <strong>Unify</strong>{' '}
      <code>
        {title(unifySource.itemId)}: {unifySource.path.join('.') || '(root)'}
      </code>{' '}
      ⊔{' '}
      {unifyTarget ? (
        <code>
          {title(unifyTarget.itemId)}: {unifyTarget.path.join('.') || '(root)'}
        </code>
      ) : (
        <span className="muted">click a feature (or “Select for unification”) in another feature structure…</span>
      )}{' '}
      <button type="button" className="primary small" disabled={!unifyTarget} onClick={() => void unify()}>
        Unify
      </button>{' '}
      <button type="button" className="small" onClick={clearUnify}>
        Cancel
      </button>
    </div>
  )
}

export function FeedPage() {
  const { status } = useApp()
  const { items, lastAdded, clear } = useFeed()
  const seen = useRef<number | null>(null)
  // newest first, right under the composer
  const newestFirst = useMemo(() => [...items].reverse(), [items])

  // A new entry appears at the top of the feed: bring it into view.
  useEffect(() => {
    if (lastAdded === null || lastAdded === seen.current) return
    seen.current = lastAdded
    document.querySelector('.app-main')?.scrollTo?.({ top: 0, behavior: 'smooth' })
  }, [lastAdded])

  if (status && !status.activeGrammar) return <GrammarRequired />

  return (
    <div className="page feed-page">
      <div className="composer-dock">
        <Composer />
        <UnifyBar />
      </div>
      {items.length > 0 && (
        <div className="row feed-tools">
          <span className="muted small grow">
            {items.length} item{items.length === 1 ? '' : 's'}, newest first
          </span>
          <button type="button" className="small" onClick={clear}>
            Clear feed
          </button>
        </div>
      )}
      {!items.length && (
        <div className="empty feed-empty">
          <p>
            Parse a sentence, generate from an MRS, or look up a type, lexical entry or rule of <strong>{status?.activeGrammar?.name}</strong>.
          </p>
          <p className="small">
            Results are added to the top of this feed. Click any node of a parse tree to add its feature structure; click features in two
            feature structures to unify them.
          </p>
        </div>
      )}
      <div className="feed" aria-live="polite">
        {newestFirst.map((it) => (
          <FeedItemView key={it.id} item={it} />
        ))}
      </div>
    </div>
  )
}
