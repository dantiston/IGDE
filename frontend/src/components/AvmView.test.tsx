import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Avm } from '../types'
import { AvmView, asList } from './AvmView'

const node = (type: string, features: [string, Avm][] = [], tag: number | null = null): Avm => ({ type, tag, features })

// [ sign STEM < "n1", "x" >  SYNSEM [1] [ synsem LOCAL local ]  KEY [1] ]
const avm = node('sign', [
  ['STEM', node('cons', [['FIRST', node('"n1"')], ['REST', node('cons', [['FIRST', node('"x"')], ['REST', node('null')]])]])],
  ['SYNSEM', node('synsem', [['LOCAL', node('local', [['CAT', node('cat', [['HEAD', node('noun')]])]])]], 1)],
  ['KEY', { ref: 1 }],
])

describe('asList', () => {
  it('reads FIRST/REST chains', () => {
    const stem = (avm as { features: [string, Avm][] }).features[0][1]
    const l = asList(stem, ['STEM'])!
    expect(l.items.map((i) => (i.avm as { type: string }).type)).toEqual(['"n1"', '"x"'])
    expect(l.items[1].path).toEqual(['STEM', 'REST', 'FIRST'])
    expect(l.tail).toBeNull()
  })
  it('keeps an open tail', () => {
    const open = node('cons', [['FIRST', node('a')], ['REST', node('list')]])
    expect(asList(open, [])!.tail?.path).toEqual(['REST'])
    expect(asList(node('sign'), [])).toBeNull()
  })
})

describe('AvmView', () => {
  it('renders types, features, lists and coreference tags', () => {
    render(<AvmView avm={avm} />)
    expect(screen.getByText('sign')).toBeInTheDocument()
    expect(screen.getByText('"n1"')).toBeInTheDocument()
    expect(screen.getAllByText('⟨')).toHaveLength(1)
    expect(screen.getAllByText('1')).toHaveLength(2) // tag + reference
  })

  it('collapses below the default depth and expands on demand', () => {
    render(<AvmView avm={avm} defaultDepth={2} />)
    expect(screen.queryByText('noun')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /local/ }))
    fireEvent.click(screen.getByRole('button', { name: /cat/ }))
    expect(screen.getByText('noun')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse' }))
    expect(screen.queryByText('synsem')).toBeInTheDocument()
    expect(screen.queryByText('LOCAL')).not.toBeInTheDocument()
  })

  it('can show lists as FIRST/REST', () => {
    render(<AvmView avm={avm} />)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(screen.getAllByText('FIRST').length).toBeGreaterThan(0)
  })

  it('reports feature paths for unification and opens the failure path', () => {
    const onPathClick = vi.fn()
    render(<AvmView avm={avm} defaultDepth={1} onPathClick={onPathClick} failurePath={['SYNSEM', 'LOCAL', 'CAT', 'HEAD']} />)
    expect(screen.getByText('noun')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'HEAD' }))
    expect(onPathClick).toHaveBeenCalledWith(['SYNSEM', 'LOCAL', 'CAT', 'HEAD'])
  })
})
