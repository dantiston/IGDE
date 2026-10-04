import type {
  AvmDoc,
  FsFile,
  FsListing,
  GenerateResponse,
  Grammar,
  HierarchyNode,
  ParseResponse,
  Settings,
  Status,
  TfsLookup,
  TfsParse,
  AceStatus,
  AceProcess,
} from './types'

export class ApiError extends Error {
  status: number
  data: Record<string, unknown>
  constructor(message: string, status: number, data: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.data = data
  }
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin', headers: {} }
  if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }
  } else if (method !== 'GET') {
    init.headers = { 'X-CSRFToken': csrfToken() }
  }
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError('Cannot reach the IGDE server. Is `python manage.py runserver` running?', 0)
  }
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    throw new ApiError(`Unexpected response from server (${res.status})`, res.status)
  }
  if (!res.ok) {
    const d = (data ?? {}) as Record<string, unknown>
    throw new ApiError(String(d.error ?? `Request failed (${res.status})`), res.status, d)
  }
  return data as T
}

const q = (params: Record<string, string | number | boolean | undefined>) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => [k, String(v)]),
  ).toString()

export const api = {
  status: () => request<Status>('GET', '/api/status'),
  saveSettings: (s: Partial<Settings> & { force?: boolean }) =>
    request<{ settings: Settings; ace: AceStatus }>('PUT', '/api/settings', s),
  testAce: (aceRoot: string) => request<AceStatus>('POST', '/api/settings/test-ace', { aceRoot }),

  fsRoots: () => request<{ roots: { name: string; path: string }[] }>('GET', '/api/fs/roots'),
  fsList: (path?: string, hidden = false) =>
    request<FsListing>('GET', `/api/fs/list?${q({ path, hidden: hidden ? 1 : undefined })}`),
  fsRead: (path: string) => request<FsFile>('GET', `/api/fs/file?${q({ path })}`),
  fsWrite: (path: string, content: string, expectedMtime?: number) =>
    request<{ path: string; size: number; mtime: number }>('PUT', '/api/fs/file', {
      path,
      content,
      expectedMtime,
    }),
  detectGrammar: (path: string) =>
    request<{ kind: 'source' | 'image'; configPath?: string; imagePath?: string; name: string; grammarTop?: string }>(
      'GET',
      `/api/fs/detect-grammar?${q({ path })}`,
    ),

  grammars: () => request<{ grammars: Grammar[] }>('GET', '/api/grammars'),
  addGrammar: (g: { name?: string; configPath?: string; imagePath?: string; compile?: boolean }) =>
    request<{ grammar: Grammar; compileError?: string }>('POST', '/api/grammars', g),
  grammar: (id: number) => request<{ grammar: Grammar }>('GET', `/api/grammars/${id}`),
  updateGrammar: (id: number, g: { name?: string; imagePath?: string }) =>
    request<{ grammar: Grammar }>('PATCH', `/api/grammars/${id}`, g),
  removeGrammar: (id: number) => request<{ deleted: number }>('DELETE', `/api/grammars/${id}`),
  activateGrammar: (id: number) => request<{ activeGrammar: Grammar }>('POST', `/api/grammars/${id}/activate`, {}),
  compileGrammar: (id: number) => request<{ grammar: Grammar }>('POST', `/api/grammars/${id}/compile`, {}),
  grammarFiles: (id: number) =>
    request<{ root: string; files: { path: string; rel: string; size: number }[] }>(
      'GET',
      `/api/grammars/${id}/files`,
    ),

  parse: (sentence: string, grammar?: number, n?: number) =>
    request<ParseResponse>('POST', '/api/parse', { sentence, grammar, n }),
  generate: (mrs: string, grammar?: number, n?: number) =>
    request<GenerateResponse>('POST', '/api/generate', { mrs, grammar, n }),

  processes: () => request<{ processes: AceProcess[] }>('GET', '/api/processes'),
  stopProcess: (key?: string) => request<{ processes: AceProcess[] }>('POST', '/api/processes/stop', { key }),

  tfsParse: (sentence: string, grammar?: number) =>
    request<TfsParse>('POST', '/api/tfs/parse', { sentence, grammar }),
  tfsNode: (id: number, session: number, grammar?: number, what: 'avm' | 'mrs' = 'avm') =>
    request<AvmDoc & { session: number }>('POST', '/api/tfs/node', { id, session, grammar, what }),
  tfsLookup: (kind: 'type' | 'lex' | 'rule' | 'instance', name: string, grammar?: number) =>
    request<TfsLookup>('POST', '/api/tfs/lookup', { kind, name, grammar }),
  tfsHierarchy: (type: string, grammar?: number) =>
    request<{ session: number; name: string; nodes: HierarchyNode[] }>('POST', '/api/tfs/hierarchy', {
      type,
      grammar,
    }),
  tfsUnify: (
    left: { id: number; path: string[] },
    right: { id: number; path: string[] },
    session: number,
    grammar?: number,
  ) =>
    request<{ session: number; ok: boolean; id?: number; title?: string; avm?: AvmDoc['avm']; failure?: AvmDoc['failure']; message?: string }>(
      'POST',
      '/api/tfs/unify',
      { left, right, session, grammar },
    ),
}
