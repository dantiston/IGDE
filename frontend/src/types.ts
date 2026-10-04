export interface AceStatus {
  ok: boolean
  source: 'settings' | 'env' | 'path' | 'homebrew' | null
  aceRoot: string | null
  executable: string | null
  version: string | null
  error: string | null
}

export interface Settings {
  aceRoot: string
  maxResults: number
  timeoutSeconds: number
  maxChartMegabytes: number
  maxUnpackMegabytes: number
  grammarImageDir: string
  defaultGrammarImageDir: string
  activeGrammar: number | null
}

export interface Grammar {
  id: number
  name: string
  kind: 'source' | 'image'
  configPath: string
  imagePath: string
  rootDir: string
  image: { exists: boolean; size: number | null; mtime: number | null }
  compileStatus: 'idle' | 'running' | 'ok' | 'failed'
  compiledAt: string | null
  compileLog?: string
}

export interface AceProcess {
  key: string
  kind: 'parser' | 'generator' | 'lui'
  grammarId: number
  grammarName: string
  pid: number
  alive: boolean
  started: number
  lastUsed: number
  requests: number
  session?: number
}

export interface Status {
  ace: AceStatus
  settings: Settings
  activeGrammar: Grammar | null
  grammars: Grammar[]
  processes: AceProcess[]
  igdeHome: string
  envAceRoot: string | null
}

export type FsHint = 'grammar-dir' | 'config' | 'image' | 'source' | null

export interface FsEntry {
  name: string
  path: string
  kind: 'dir' | 'file'
  size: number | null
  mtime: number | null
  hint: FsHint
}

export interface FsListing {
  path: string
  parent: string | null
  entries: FsEntry[]
  hint: FsHint
}

export interface FsFile {
  path: string
  content: string
  size: number
  mtime: number
  writable: boolean
}

/* ---- processing results ---- */

export interface DerivationNode {
  id?: number
  entity: string
  score?: number
  start?: number
  end?: number
  form?: string
  type?: string
  daughters?: DerivationNode[]
}

export interface LabelledNode {
  label?: string | null
  form?: string
  children?: LabelledNode[]
}

export interface MrsJson {
  top?: string
  index?: string
  relations: {
    label: string
    predicate: string
    arguments: Record<string, string>
    lnk?: { from: number; to: number }
  }[]
  constraints?: { relation: string; high: string; low: string }[]
  variables?: Record<string, { type?: string; properties?: Record<string, string> }>
}

export interface DmrsJson {
  top?: number
  index?: number
  nodes: {
    nodeid: number
    predicate: string
    carg?: string
    lnk?: { from: number; to: number }
    sortinfo?: Record<string, string>
  }[]
  links: { from: number; to: number; rargname: string; post: string }[]
}

export interface ParseResult {
  id: number
  score: number | null
  probability: number | null
  derivation: DerivationNode | null
  signature: string[]
  tree: LabelledNode | null
  mrsString: string | null
  simplemrs: string | null
  mrs?: MrsJson
  dmrs?: DmrsJson | null
  simpledmrs?: string | null
  eds?: string | null
}

interface ResponseCommon {
  grammar: number
  input: string | null
  readings: number | null
  error: string | null
  notes: string[]
  warnings: string[]
  errors: string[]
  time: number | null
  pedges: number | null
  aedges: number | null
}

export interface ParseResponse extends ResponseCommon {
  results: ParseResult[]
}

export interface Realization {
  id: number
  surface: string
  score: number | null
  probability: number | null
  derivation: DerivationNode | null
  tree: LabelledNode | null
}

export interface GenerateResponse extends ResponseCommon {
  results: Realization[]
}

/* ---- TFS / LUI ---- */

export type Avm = AvmNode | AvmRef
export interface AvmNode {
  type: string
  tag: number | null
  features: [string, Avm][]
}
export interface AvmRef {
  ref: number
}

export interface LuiTree {
  id: number
  label: string
  eid: number
  entity: string
  form?: string
  children: LuiTree[]
  signature?: string[]
}

export interface TfsParse {
  grammar: number
  session: number
  sentence: string
  count: number
  chart: number | null
  trees: LuiTree[]
  output: string
}

export interface UnifyFailure {
  kind: string
  path: string[]
  types: string[]
}

export interface AvmDoc {
  /** LUI object id ACE assigned to this AVM; usable for unification. */
  id: number
  title: string
  avm: Avm
  failure?: UnifyFailure | null
  definition?: { name: string; file: string; line: number; tdl: string; path?: string } | null
}

export interface TfsLookup {
  session: number
  avm?: Avm
  id?: number
  title?: string
  definition?: AvmDoc['definition']
  matches?: string[]
  more?: string | null
  message?: string
}

export interface HierarchyNode {
  name: string
  parents: number[]
  children: number[]
}
