import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

afterEach(() => vi.restoreAllMocks())

test('loads and displays the frozen incident catalog', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [{
      incident_id: 'CC-001',
      date: '2026-07-06',
      window_start: '2026-07-06T08:00:00',
      window_end: '2026-07-06T11:45:00',
      incident_start: '2026-07-06T09:15:00',
      alert: 'Service level fell below target.',
    }],
  }))

  render(<App />)

  expect(screen.getByRole('heading', { name: /contact center incident investigator/i })).toBeInTheDocument()
  expect(await screen.findByRole('option', { name: /CC-001/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /run baseline/i })).toBeEnabled()
})

