import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TreeView, fromDerivation, fromLabelled, fromLui, layoutTree } from './Tree'

describe('tree adapters', () => {
  it('folds preterminals of labelled trees', () => {
    const t = fromLabelled({ label: 'S', children: [{ label: 'N', children: [{ form: 'dogs' }] }, { label: 'V', children: [{ form: 'bark' }] }] })
    expect(t.children.map((c) => [c.label, c.form])).toEqual([
      ['N', 'dogs'],
      ['V', 'bark'],
    ])
  })
  it('converts derivations and LUI trees', () => {
    const d = fromDerivation({ entity: 'subj-head', id: 8, daughters: [{ entity: 'n1', form: 'n1' }, { entity: 'iv', form: 'iv' }] })
    expect(d.label).toBe('subj-head')
    expect(d.children[1].form).toBe('iv')
    const l = fromLui({ id: 1, label: 'S', eid: 8, entity: 'subj-head', children: [{ id: 2, label: 'N', eid: 3, entity: 'n1', form: 'n1', children: [] }] }, false)
    expect([l.key, l.label, l.sub]).toEqual(['1', 'S', 'subj-head'])
    expect(fromLui({ id: 1, label: 'S', eid: 8, entity: 'subj-head', children: [] }, true).label).toBe('subj-head')
  })
  it('lays children out left to right under their parent', () => {
    const { placed } = layoutTree(fromLabelled({ label: 'S', children: [{ label: 'A', children: [{ form: 'a' }] }, { label: 'B', children: [{ form: 'b' }] }] }))
    const [a, b] = placed.children
    expect(a.x).toBeLessThan(b.x)
    expect(placed.x).toBeCloseTo((a.x + b.x) / 2)
    expect(a.y).toBeGreaterThan(placed.y)
  })
})

describe('TreeView', () => {
  it('selects nodes by click and keyboard', () => {
    const onSelect = vi.fn()
    const root = fromLui({ id: 1, label: 'S', eid: 8, entity: 'subj-head', children: [{ id: 2, label: 'N', eid: 3, entity: 'n1', form: 'n1', children: [] }] }, false)
    render(<TreeView root={root} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /^N/ }))
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ key: '2' }))
    fireEvent.keyDown(screen.getByRole('button', { name: /^S/ }), { key: 'Enter' })
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ key: '1' }))
    expect(screen.getByText('n1', { selector: '.tree-word' })).toBeInTheDocument()
  })
})
