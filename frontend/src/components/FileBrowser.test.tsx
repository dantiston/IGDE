import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FileBrowser } from './FileBrowser'

const listings: Record<string, unknown> = {
  '/home/me': {
    path: '/home/me',
    parent: '/home',
    hint: null,
    entries: [
      { name: 'erg', path: '/home/me/erg', kind: 'dir', size: null, mtime: 1, hint: 'grammar-dir' },
      { name: 'erg.dat', path: '/home/me/erg.dat', kind: 'file', size: 2048, mtime: 1, hint: 'image' },
    ],
  },
  '/home/me/erg': {
    path: '/home/me/erg',
    parent: '/home/me',
    hint: 'grammar-dir',
    entries: [{ name: 'english.tdl', path: '/home/me/erg/english.tdl', kind: 'file', size: 10, mtime: 1, hint: 'source' }],
  },
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const u = new URL(url, 'http://x')
      if (u.pathname === '/api/fs/roots') return new Response(JSON.stringify({ roots: [{ name: 'Home', path: '/home/me' }] }))
      const path = u.searchParams.get('path') ?? '/home/me'
      const body = listings[path]
      return body ? new Response(JSON.stringify(body)) : new Response(JSON.stringify({ error: `${path} does not exist.` }), { status: 404 })
    }),
  )
})
afterEach(() => vi.unstubAllGlobals())

describe('FileBrowser', () => {
  it('lists a directory with grammar hints and navigates into folders', async () => {
    const onOpenFile = vi.fn()
    render(<FileBrowser initialPath="/home/me" onOpenFile={onOpenFile} />)
    expect(await screen.findByText('grammar image')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^📁\s*erg/ }))
    await screen.findByText('english.tdl')
    fireEvent.click(screen.getByRole('button', { name: /english\.tdl/ }))
    expect(onOpenFile).toHaveBeenCalledWith(expect.objectContaining({ path: '/home/me/erg/english.tdl' }))
    expect(screen.getByLabelText('Path')).toHaveValue('/home/me/erg')
  })

  it('picks folders and files', async () => {
    const onPick = vi.fn()
    const { rerender } = render(<FileBrowser initialPath="/home/me" mode="pick-dir" onPick={onPick} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Choose this folder' }))
    expect(onPick).toHaveBeenCalledWith('/home/me')
    rerender(<FileBrowser initialPath="/home/me" mode="pick-file" accept={(e) => e.hint === 'image'} onPick={onPick} />)
    fireEvent.click(await screen.findByRole('button', { name: /erg\.dat/ }))
    expect(onPick).toHaveBeenLastCalledWith('/home/me/erg.dat', expect.objectContaining({ name: 'erg.dat' }))
  })

  it('goes to a typed path and shows errors', async () => {
    render(<FileBrowser initialPath="/home/me" />)
    await screen.findByText('erg.dat')
    fireEvent.change(screen.getByLabelText('Path'), { target: { value: '/nowhere' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    await screen.findByText('/nowhere does not exist.')
    fireEvent.change(screen.getByLabelText('Path'), { target: { value: '/home/me/erg' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    await waitFor(() => expect(screen.getByText('english.tdl')).toBeInTheDocument())
  })
})
