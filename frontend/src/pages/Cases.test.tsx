import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { type Case, api } from '../api/client'
import { CaseProvider } from '../state/CaseContext'
import { CasesPage } from './Cases'

const existing: Case = {
  id: 'c-1',
  name: 'Device A',
  examiner: 'Sam',
  timezone: 'Asia/Kolkata',
  notes: '',
  created_at: '2024-06-15T10:00:00.000Z',
  updated_at: '2024-06-15T10:00:00.000Z',
  event_count: 1234,
  artifact_count: 2,
  session_count: 7,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <CaseProvider>
        <CasesPage />
      </CaseProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(api, 'listCases').mockResolvedValue([existing])
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CasesPage', () => {
  it('lists cases with their counts', async () => {
    renderPage()
    expect(await screen.findByText('Device A')).toBeInTheDocument()
    expect(screen.getByText('1,234')).toBeInTheDocument()
    expect(screen.getByText('Asia/Kolkata')).toBeInTheDocument()
  })

  it('keeps "Create" disabled until the form is valid, and explains a bad timezone', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Device A')
    const create = screen.getByRole('button', { name: 'Create & acquire' })
    expect(create).toBeDisabled()

    await user.type(screen.getByLabelText('Case name'), 'New case')
    expect(create).toBeEnabled()

    const tz = screen.getByLabelText(/Device timezone/)
    await user.clear(tz)
    await user.type(tz, 'Mars/Olympus')
    expect(create).toBeDisabled()
    expect(screen.getByText(/Unknown timezone/)).toBeInTheDocument()

    await user.clear(tz)
    await user.type(tz, 'America/New_York')
    expect(create).toBeEnabled()
  })

  it('sends the trimmed timezone when creating a case', async () => {
    const user = userEvent.setup()
    const createCase = vi.spyOn(api, 'createCase').mockResolvedValue({ ...existing, id: 'c-2', name: 'New case' })
    renderPage()
    await screen.findByText('Device A')
    await user.type(screen.getByLabelText('Case name'), 'New case')
    await user.type(screen.getByLabelText('Examiner'), 'Sam')
    await user.click(screen.getByRole('button', { name: 'Create & acquire' }))
    await waitFor(() => expect(createCase).toHaveBeenCalledOnce())
    expect(createCase.mock.calls[0][0]).toMatchObject({ name: 'New case', examiner: 'Sam', timezone: 'UTC' })
  })

  it('surfaces server-side errors instead of swallowing them', async () => {
    vi.spyOn(api, 'listCases').mockRejectedValue(new Error('Cannot reach the Fuseline API.'))
    renderPage()
    expect(await screen.findByText('Cannot reach the Fuseline API.')).toBeInTheDocument()
  })
})
