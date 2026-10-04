/** Whether a processor could be found and run (from its backend's check). */
export interface ProcessorStatus {
  ok: boolean
  /** how the executable was found: a key of Backend.sources */
  source: string | null
  location: string | null
  executable: string | null
  version: string | null
  error: string | null
}

export type Capability = 'parse' | 'generate' | 'tfs' | 'compile'

export interface BackendOption {
  key: string
  label: string
  default: number | string
  help: string
  type: 'int' | 'str'
  min: number | null
  max: number | null
}

/** A kind of processor IGDE can drive (e.g. ACE). */
export interface Backend {
  key: string
  label: string
  description: string
  homepage: string
  capabilities: Capability[]
  options: BackendOption[]
  locationLabel: string
  locationHelp: string
  sources: Record<string, string>
  installCommand: string
  envVars: Record<string, string | null>
  configLabel: string
  imageSuffixes: string[]
}

/** A configured processor: a backend, where it's installed and its options. */
export interface Processor {
  id: number
  name: string
  backend: string
  backendLabel: string
  location: string
  options: Record<string, number | string>
  isDefault: boolean
  grammars: number
  status: ProcessorStatus
}

export interface Install {
  backend: string
  backendLabel: string
  source: string
  path: string
  version: string
}

export interface Settings {
  defaultProcessor: number | null
  maxResults: number
  timeoutSeconds: number
  grammarImageDir: string
  defaultGrammarImageDir: string
  profilesDir: string
  defaultProfilesDir: string
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
  /** its processor; null means the default one */
  processor: number | null
  compileLog?: string
}

export interface ProcessorProcess {
  key: string
  kind: 'parser' | 'generator' | 'lui'
  grammarId: number
  grammarName: string
  processorName: string
  pid: number
  alive: boolean
  started: number
  lastUsed: number
  requests: number
  session?: number
}

export interface Status {
  /** the processor the workbench uses (the active grammar's) */
  processor: Processor | null
  processors: Processor[]
  backends: Backend[]
  settings: Settings
  activeGrammar: Grammar | null
  grammars: Grammar[]
  processes: ProcessorProcess[]
  igdeHome: string
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
  /** LUI object id the processor assigned to this AVM; usable for unification. */
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

/* ---- test suites ([incr tsdb()] profiles) ---- */

export interface ProfileStats {
  items: number
  wellformed: number
  illformed: number
  processed: number
  parsed: number
  coverage: number | null
  overgeneration: number | null
  errors: number
  avgReadings: number | null
  avgTime: number | null
  runInfo: { application?: string; grammar?: string; start?: string; end?: string; user?: string; host?: string } | null
  error?: string
}

export interface Profile {
  id: number
  name: string
  path: string
  kind: 'suite' | 'run'
  suite: number | null
  grammar: number | null
  grammarName: string
  owned: boolean
  created: string | null
  runStatus: 'idle' | 'running' | 'ok' | 'failed' | 'cancelled'
  exists: boolean
  progress: { done: number; total: number; started: number } | null
  stats: ProfileStats | null
  runLog?: string
  rows?: ProfileRow[]
}

export interface ProfileRow {
  id: number
  input: string
  wf: number
  comment: string
  processed: boolean
  readings?: number | null
  time?: number | null
  error?: string | null
  results?: number
}

export type CompareStatus = 'gained' | 'lost' | 'changed' | 'readings' | 'same' | 'missing'

export interface Comparison {
  items: Record<string, { status: CompareStatus; readings: number | null; otherReadings: number | null }>
  counts: Partial<Record<CompareStatus, number>>
}

export interface ItemResults {
  item: { id: number; input: string; wf: number; comment: string }
  processed: boolean
  readings?: number | null
  error?: string | null
  time?: number | null
  results: (ParseResult & { surface?: string | null })[]
}
