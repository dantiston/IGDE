import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../api'
import type { FsFile } from '../types'

export interface FileEditorProps {
  path: string
  line?: number
  onSaved?: (path: string) => void
  onDirtyChange?: (dirty: boolean) => void
}

const LINE_H = 18

export function FileEditor({ path, line, onSaved, onDirtyChange }: FileEditorProps) {
  const [file, setFile] = useState<FsFile | null>(null)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const area = useRef<HTMLTextAreaElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const dirty = file !== null && text !== file.content

  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange])

  const load = useCallback(async () => {
    setError(null)
    setConflict(false)
    try {
      const f = await api.fsRead(path)
      setFile(f)
      setText(f.content)
      setSavedAt(null)
    } catch (e) {
      setFile(null)
      setError((e as Error).message)
    }
  }, [path])

  useEffect(() => {
    void load()
  }, [load])

  // Jump to the requested line once the file is loaded.
  useEffect(() => {
    const ta = area.current
    if (!ta || !file || !line) return
    const lines = file.content.split('\n')
    const start = lines.slice(0, line - 1).reduce((s, l) => s + l.length + 1, 0)
    const end = start + (lines[line - 1]?.length ?? 0)
    ta.focus()
    ta.setSelectionRange(start, end)
    ta.scrollTop = Math.max(0, (line - 10) * LINE_H)
  }, [file, line])

  const save = useCallback(
    async (force = false) => {
      if (!file) return
      setSaving(true)
      setError(null)
      try {
        const r = await api.fsWrite(path, text, force ? undefined : file.mtime)
        setFile({ ...file, content: text, mtime: r.mtime, size: r.size })
        setConflict(false)
        setSavedAt(Date.now())
        onSaved?.(path)
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) setConflict(true)
        setError((e as Error).message)
      } finally {
        setSaving(false)
      }
    },
    [file, path, text, onSaved],
  )

  const lineCount = useMemo(() => text.split('\n').length, [text])

  return (
    <div className="editor">
      <div className="editor-bar">
        <span className="editor-path" title={path}>
          {path}
          {dirty && <span className="dirty" aria-label="unsaved changes"> ●</span>}
        </span>
        {file && !file.writable && <span className="badge warn">read-only</span>}
        {savedAt && !dirty && <span className="muted">saved</span>}
        <button type="button" onClick={() => void load()} disabled={saving}>
          Reload
        </button>
        <button type="button" className="primary" onClick={() => void save()} disabled={!dirty || saving || !file?.writable}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && (
        <div className="error">
          {error}
          {conflict && (
            <>
              {' '}
              <button type="button" onClick={() => void save(true)}>
                Overwrite anyway
              </button>
            </>
          )}
        </div>
      )}
      {file && (
        <div className="editor-body">
          <div className="editor-gutter" ref={gutter} aria-hidden>
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i} className={line === i + 1 ? 'hl' : ''}>
                {i + 1}
              </div>
            ))}
          </div>
          <textarea
            ref={area}
            aria-label={`Contents of ${path}`}
            className="editor-text"
            value={text}
            spellCheck={false}
            wrap="off"
            onChange={(e) => setText(e.target.value)}
            onScroll={(e) => {
              if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop
            }}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault()
                void save()
              } else if (e.key === 'Tab' && !e.shiftKey) {
                e.preventDefault()
                const t = e.currentTarget
                const { selectionStart: s, selectionEnd: en } = t
                setText(text.slice(0, s) + '  ' + text.slice(en))
                requestAnimationFrame(() => t.setSelectionRange(s + 2, s + 2))
              }
            }}
          />
        </div>
      )}
    </div>
  )
}
