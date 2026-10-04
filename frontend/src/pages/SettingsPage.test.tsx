import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppProvider } from '../state'
import type { Backend, Processor, Status } from '../types'
import { SettingsPage } from './SettingsPage'

// Nothing on the page is specific to one processor: a made-up backend's
// location label and options come from its description.
const backend = (key: string, label: string, options: Backend['options'] = []): Backend => ({
  key,
  label,
  description: `${label} parses things.`,
  homepage: '',
  capabilities: ['parse', 'generate'],
  options,
  locationLabel: `${label.toUpperCase()}_HOME`,
  locationHelp: `Where ${label} lives.`,
  sources: { settings: `${label.toUpperCase()}_HOME` },
  installCommand: '',
  envVars: {},
  configLabel: `${label} config`,
  imageSuffixes: ['.img'],
})

const backends = [
  backend('ace', 'ACE'),
  backend('pet', 'PET', [{ key: 'memory', label: 'Memory (MB)', default: 500, help: '', type: 'int', min: 1, max: null }]),
]

const processor = (p: Partial<Processor>): Processor => ({
  id: 1,
  name: 'ACE',
  backend: 'ace',
  backendLabel: 'ACE',
  location: '',
  options: {},
  isDefault: true,
  grammars: 0,
  status: { ok: true, source: 'settings', location: '/opt/ace', executable: '/opt/ace/ace', version: '0.9.34', error: null },
  ...p,
})

const status = (): Status => ({
  processor: processor({}),
  processors: [
    processor({}),
    processor({
      id: 2,
      name: 'My PET',
      backend: 'pet',
      backendLabel: 'PET',
      isDefault: false,
      location: '/opt/pet',
      options: { memory: 500 },
      status: { ok: false, source: 'settings', location: '/opt/pet', executable: null, version: null, error: 'cheap not found' },
    }),
  ],
  backends,
  settings: {
    defaultProcessor: 1,
    maxResults: 5,
    timeoutSeconds: 60,
    grammarImageDir: '',
    defaultGrammarImageDir: '/home/me/.igde/grammars',
    profilesDir: '',
    defaultProfilesDir: '/home/me/.igde/profiles',
    activeGrammar: null,
  },
  activeGrammar: null,
  grammars: [],
  processes: [],
  igdeHome: '/home/me/.igde',
})

let calls: { method: string; url: string; body: unknown }[] = []

beforeEach(() => {
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(String(init.body)) : undefined
      calls.push({ method: init?.method ?? 'GET', url, body })
      let data: unknown = {}
      if (url === '/api/status') data = status()
      else if (url === '/api/processors/detect') data = { found: [] }
      else if (url.startsWith('/api/processors/')) data = { processor: { ...status().processors[1], ...body } }
      return new Response(JSON.stringify(data), { status: 200 })
    }),
  )
})

afterEach(() => vi.unstubAllGlobals())

describe('SettingsPage', () => {
  it('lists processors of any backend and edits their options', async () => {
    render(
      <AppProvider>
        <SettingsPage />
      </AppProvider>,
    )
    const cards = await screen.findAllByTestId('processor')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('ACE 0.9.34')).toBeInTheDocument()
    expect(within(cards[0]).getByText('default')).toBeInTheDocument()
    const pet = cards[1]
    expect(within(pet).getByText('PET not available')).toBeInTheDocument()
    expect(within(pet).getByText('cheap not found')).toBeInTheDocument()

    fireEvent.click(within(pet).getByRole('button', { name: 'Edit' }))
    fireEvent.change(within(pet).getByLabelText('PET_HOME'), { target: { value: '/usr/local/pet' } })
    fireEvent.change(within(pet).getByRole('spinbutton'), { target: { value: '800' } })
    fireEvent.click(within(pet).getByRole('button', { name: 'Save processor' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')).toEqual({
      method: 'PUT',
      url: '/api/processors/2',
      body: { name: 'My PET', location: '/usr/local/pet', options: { memory: 800 } },
    })

    fireEvent.click(within(pet).getByRole('button', { name: 'Make default' }))
    await waitFor(() =>
      expect(calls.find((c) => c.url === '/api/settings')).toMatchObject({ method: 'PUT', body: { defaultProcessor: 2 } }),
    )
  })
})
