/**
 * The workbench feed: every parse, generation, feature structure, lookup and
 * hierarchy the user asks for is appended to one running list, newest last.
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from '../api'
import { useApp } from '../state'
import type { Avm, AvmDoc, GenerateResponse, HierarchyNode, LuiTree, ParseResponse, TfsParse } from '../types'

export type Loading<T> = { status: 'loading' } | { status: 'done'; data: T } | { status: 'error'; error: string }
export type LookupKind = 'type' | 'lex' | 'rule' | 'instance'

export const KIND_LABEL: Record<LookupKind, string> = {
  type: 'Type',
  lex: 'Lexical entry',
  rule: 'Rule',
  instance: 'Instance',
}

interface Base {
  id: number
  grammarId: number
  grammarName: string
  time: number
}

export type FeedItem = Base &
  (
    | { kind: 'parse'; sentence: string; state: Loading<ParseResponse> }
    | { kind: 'generate'; mrs: string; origin: string; state: Loading<GenerateResponse> }
    | { kind: 'avm'; title: string; origin: string; doc: AvmDoc; session: number; rootType?: string }
    | { kind: 'hierarchy'; type: string; state: Loading<HierarchyNode[]> }
    | { kind: 'lookup'; lookupKind: LookupKind; name: string; matches: string[]; more?: string | null }
  )

export type ItemOf<K extends FeedItem['kind']> = Extract<FeedItem, { kind: K }>

/** A feed item before it's added (Omit distributed over the union). */
type NewItem = FeedItem extends infer T ? (T extends FeedItem ? Omit<T, 'id' | 'time'> : never) : never

/** A substructure picked for interactive unification. */
export interface PathRef {
  itemId: number
  path: string[]
}

interface FeedState {
  items: FeedItem[]
  parse: (sentence: string, n?: number) => void
  generate: (mrs: string, origin: string, n?: number) => void
  inspectNode: (item: ItemOf<'parse'>, resultIndex: number, path: number[], label: string) => Promise<void>
  lookup: (kind: LookupKind, name: string, grammarId?: number) => Promise<void>
  hierarchy: (type: string, grammarId?: number) => void
  unifySource: PathRef | null
  unifyTarget: PathRef | null
  pickPath: (ref: PathRef) => void
  clearUnify: () => void
  unify: () => Promise<void>
  remove: (id: number) => void
  clear: () => void
  lastAdded: number | null
}

const Ctx = createContext<FeedState | null>(null)

const rootTypeOf = (a: Avm) => ('type' in a ? a.type : undefined)

function nodeAtPath(t: LuiTree, path: number[]): LuiTree | null {
  let cur: LuiTree | undefined = t
  for (const i of path) cur = cur?.children[i]
  return cur ?? null
}

export function FeedProvider({ children }: { children: ReactNode }) {
  const { status, notify } = useApp()
  const [items, setItems] = useState<FeedItem[]>([])
  const [unifySource, setSource] = useState<PathRef | null>(null)
  const [unifyTarget, setTarget] = useState<PathRef | null>(null)
  const [lastAdded, setLastAdded] = useState<number | null>(null)
  const nextId = useRef(1)
  // LUI parse of each parse item's sentence, made on demand for TFS browsing
  const luiParses = useRef(new Map<number, Promise<TfsParse>>())

  const grammar = status?.activeGrammar ?? null

  const add = useCallback((item: NewItem) => {
    const id = nextId.current++
    setItems((xs) => [...xs, { ...item, id, time: Date.now() } as FeedItem])
    setLastAdded(id)
    return id
  }, [])

  const update = useCallback((id: number, patch: Partial<FeedItem>) => {
    setItems((xs) => xs.map((x) => (x.id === id ? ({ ...x, ...patch } as FeedItem) : x)))
  }, [])

  const requireGrammar = useCallback(() => {
    if (!grammar) {
      notify('No grammar selected. Add one in the Grammars tab.', 'error')
      return null
    }
    return { grammarId: grammar.id, grammarName: grammar.name }
  }, [grammar, notify])

  const parse = useCallback(
    (sentence: string, n?: number) => {
      const g = requireGrammar()
      if (!g) return
      const id = add({ kind: 'parse', sentence, state: { status: 'loading' }, ...g })
      api.parse(sentence, g.grammarId, n).then(
        (data) => update(id, { state: { status: 'done', data } }),
        (e) => update(id, { state: { status: 'error', error: (e as Error).message } }),
      )
    },
    [add, update, requireGrammar],
  )

  const generate = useCallback(
    (mrs: string, origin: string, n?: number) => {
      const g = requireGrammar()
      if (!g) return
      const id = add({ kind: 'generate', mrs, origin, state: { status: 'loading' }, ...g })
      api.generate(mrs, g.grammarId, n).then(
        (data) => update(id, { state: { status: 'done', data } }),
        (e) => update(id, { state: { status: 'error', error: (e as Error).message } }),
      )
    },
    [add, update, requireGrammar],
  )

  const addAvm = useCallback(
    (g: Pick<Base, 'grammarId' | 'grammarName'>, title: string, origin: string, doc: AvmDoc, session: number) =>
      add({ kind: 'avm', title, origin, doc, session, rootType: rootTypeOf(doc.avm), ...g }),
    [add],
  )

  const inspectNode = useCallback(
    async (item: ItemOf<'parse'>, resultIndex: number, path: number[], label: string) => {
      if (item.state.status !== 'done') return
      const result = item.state.data.results[resultIndex]
      const g = { grammarId: item.grammarId, grammarName: item.grammarName }
      const luiParse = (fresh: boolean) => {
        let p = luiParses.current.get(item.id)
        if (!p || fresh) {
          p = api.tfsParse(item.sentence, item.grammarId)
          luiParses.current.set(item.id, p)
          p.catch(() => luiParses.current.delete(item.id))
        }
        return p
      }
      for (const fresh of [false, true]) {
        try {
          const lp = await luiParse(fresh)
          // ACE ranks the same way in both modes; match on the derivation to be sure
          const tree =
            lp.trees.find((t) => t.signature?.join(' ') === result.signature.join(' ')) ?? lp.trees[resultIndex]
          const node = tree ? nodeAtPath(tree, path) : null
          if (!node) throw new Error('Could not find this node in ACE’s chart.')
          const doc = await api.tfsNode(node.id, lp.session, item.grammarId)
          addAvm(g, `${label} · ${node.entity}`, `“${item.sentence}” #${resultIndex + 1}, edge ${node.eid}`, doc, doc.session)
          return
        } catch (e) {
          // ACE's TFS session restarted since: parse again once
          if (!fresh && e instanceof ApiError && e.data.stale) continue
          notify((e as Error).message, 'error')
          return
        }
      }
    },
    [addAvm, notify],
  )

  const lookup = useCallback(
    async (kind: LookupKind, name: string, grammarId?: number) => {
      const g = grammarId
        ? { grammarId, grammarName: items.find((x) => x.grammarId === grammarId)?.grammarName ?? '' }
        : requireGrammar()
      if (!g || !name.trim()) return
      try {
        const r = await api.tfsLookup(kind, name.trim(), g.grammarId)
        if (r.avm && r.id !== undefined) {
          addAvm(
            g,
            `${KIND_LABEL[kind]} ${r.title ?? name}`,
            'lookup',
            { id: r.id, title: r.title ?? name, avm: r.avm, definition: r.definition },
            r.session,
          )
        } else if (r.matches?.length) {
          add({ kind: 'lookup', lookupKind: kind, name: name.trim(), matches: r.matches, more: r.more, ...g })
        } else {
          notify(r.message || `No ${KIND_LABEL[kind].toLowerCase()} matching “${name}”`)
        }
      } catch (e) {
        notify((e as Error).message, 'error')
      }
    },
    [add, addAvm, items, notify, requireGrammar],
  )

  const hierarchy = useCallback(
    (type: string, grammarId?: number) => {
      const g = grammarId
        ? { grammarId, grammarName: items.find((x) => x.grammarId === grammarId)?.grammarName ?? '' }
        : requireGrammar()
      if (!g || !type.trim()) return
      const id = add({ kind: 'hierarchy', type: type.trim(), state: { status: 'loading' }, ...g })
      api.tfsHierarchy(type.trim(), g.grammarId).then(
        (r) => update(id, { state: { status: 'done', data: r.nodes } }),
        (e) => update(id, { state: { status: 'error', error: (e as Error).message } }),
      )
    },
    [add, update, items, requireGrammar],
  )

  const pickPath = useCallback(
    (ref: PathRef) => {
      if (!unifySource || unifyTarget) {
        setSource(ref)
        setTarget(null)
      } else {
        setTarget(ref)
      }
    },
    [unifySource, unifyTarget],
  )
  const clearUnify = useCallback(() => {
    setSource(null)
    setTarget(null)
  }, [])

  const unify = useCallback(async () => {
    const s = items.find((x) => x.id === unifySource?.itemId)
    const t = items.find((x) => x.id === unifyTarget?.itemId)
    if (!s || !t || s.kind !== 'avm' || t.kind !== 'avm' || !unifySource || !unifyTarget) return
    if (s.session !== t.session || s.grammarId !== t.grammarId) {
      notify('These feature structures come from different ACE sessions; open them again to unify them.', 'error')
      return
    }
    try {
      const r = await api.tfsUnify(
        { id: s.doc.id, path: unifySource.path },
        { id: t.doc.id, path: unifyTarget.path },
        s.session,
        s.grammarId,
      )
      const where = (p: string[]) => p.join('.') || '(root)'
      if (r.avm && r.id !== undefined) {
        addAvm(
          { grammarId: s.grammarId, grammarName: s.grammarName },
          r.ok ? 'Unification' : 'Failed unification',
          `${s.title} ${where(unifySource.path)} ⊔ ${t.title} ${where(unifyTarget.path)}`,
          { id: r.id, title: r.title ?? 'unification', avm: r.avm, failure: r.failure },
          r.session,
        )
      } else {
        notify(r.message ?? 'Unification failed', 'error')
      }
      clearUnify()
    } catch (e) {
      notify((e as Error).message, 'error')
    }
  }, [items, unifySource, unifyTarget, addAvm, notify, clearUnify])

  const remove = useCallback((id: number) => {
    setItems((xs) => xs.filter((x) => x.id !== id))
    luiParses.current.delete(id)
  }, [])
  const clear = useCallback(() => {
    setItems([])
    luiParses.current.clear()
    setSource(null)
    setTarget(null)
  }, [])

  const value = useMemo(
    () => ({
      items,
      parse,
      generate,
      inspectNode,
      lookup,
      hierarchy,
      unifySource,
      unifyTarget,
      pickPath,
      clearUnify,
      unify,
      remove,
      clear,
      lastAdded,
    }),
    [items, parse, generate, inspectNode, lookup, hierarchy, unifySource, unifyTarget, pickPath, clearUnify, unify, remove, clear, lastAdded],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFeed(): FeedState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useFeed outside FeedProvider')
  return v
}
