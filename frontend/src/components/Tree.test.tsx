import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DerivationNode, LabelledNode } from '../types'
import { TreeView, fromParse, layoutTree, pathOfKey } from './Tree'

// "the dog barks" as ACE reports it: a derivation and a labelled tree
const deriv: DerivationNode = {
  entity: 'sb-hd_mc_c',
  id: 1316,
  daughters: [
    { entity: 'sp-hd_n_c', daughters: [{ entity: 'the_1', form: 'the' }, { entity: 'n_sg_ilr', daughters: [{ entity: 'dog_n1', form: 'dog' }] }] },
    { entity: 'bark_v1', form: 'barks' },
  ],
}
const labelled: LabelledNode = {
  label: 'S',
  children: [
    { label: 'NP', children: [{ label: 'DET', children: [{ form: 'the' }] }, { label: 'N', children: [{ label: 'N', children: [{ form: 'dog' }] }] }] },
    { label: 'VP', children: [{ form: 'barks' }] },
  ],
}

describe('fromParse', () => {
  it('labels derivation nodes with the aligned labelled tree', () => {
    const t = fromParse(deriv, labelled, false)
    expect([t.label, t.sub]).toEqual(['S', 'sb-hd_mc_c'])
    const [np, vp] = t.children
    expect([np.label, np.children[1].label, np.children[1].children[0].label]).toEqual(['NP', 'N', 'N'])
    expect([vp.label, vp.form]).toEqual(['VP', 'barks'])
    expect(np.children[1].children[0].key).toBe('0.0.1.0')
    expect(pathOfKey('0.0.1.0')).toEqual([0, 1, 0])
  })
  it('falls back to rule names', () => {
    expect(fromParse(deriv, labelled, true).children[0].label).toBe('sp-hd_n_c')
    // shapes that don't line up (e.g. punctuation folded into a word) keep rule names
    const odd: LabelledNode = { label: 'S', children: [{ label: 'X', children: [{ form: 'the dog barks' }] }] }
    const t = fromParse(deriv, odd, false)
    expect(t.label).toBe('S')
    expect(t.children.map((c) => c.label)).toEqual(['sp-hd_n_c', 'bark_v1'])
    expect(fromParse(deriv, null, false).label).toBe('sb-hd_mc_c')
    // no label templates: ACE labels everything "?"
    const unknown: LabelledNode = { label: '?', children: [{ label: '?', children: [{ form: 'x' }] }, { label: '?', children: [{ form: 'y' }] }] }
    const flat: DerivationNode = { entity: 'subj-head', daughters: [{ entity: 'n1', form: 'n1' }, { entity: 'iv', form: 'iv' }] }
    expect(fromParse(flat, unknown, false).children.map((c) => c.label)).toEqual(['n1', 'iv'])
  })
  it('lays children out left to right under their parent', () => {
    const { placed } = layoutTree(fromParse(deriv, labelled, false))
    const [a, b] = placed.children
    expect(a.x).toBeLessThan(b.x)
    expect(placed.x).toBeCloseTo((a.x + b.x) / 2)
    expect(a.y).toBeGreaterThan(placed.y)
  })
})

describe('TreeView', () => {
  it('selects nodes by click and keyboard', () => {
    const onSelect = vi.fn()
    render(<TreeView root={fromParse(deriv, labelled, false)} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /^NP/ }))
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ key: '0.0' }))
    fireEvent.keyDown(screen.getByRole('button', { name: /^S \(/ }), { key: 'Enter' })
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ key: '0' }))
    expect(screen.getByText('dog', { selector: '.tree-word' })).toBeInTheDocument()
  })
})
