import { fireEvent, screen } from '@testing-library/react'
import { api } from '../../lib/api'
import { httpError, renderApp, routeGet, signIn } from '../../test/utils'
import SettingsPage from './Settings'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); signIn() })

describe('Settings → Telegram', () => {
  it('shows the Telegram tab and an unlinked account can get a link code', async () => {
    routeGet({ '/telegram/status/': { linked: false, username: '', linked_at: null } })
    vi.mocked(api.post).mockResolvedValue({ data: { code: 'ABCD-EFGH', expires_at: '2030-01-01T00:00:00Z', ttl_seconds: 600 } })
    renderApp(<SettingsPage />, { path: '/app/settings', url: '/app/settings?tab=telegram' })
    expect(await screen.findByText('Open the MEBELCHI AI bot in Telegram, press "Link account" and send the code below. The code works once and expires after a few minutes.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Get link code' }))
    expect(await screen.findByText('ABCD-EFGH')).toBeInTheDocument()
    expect(vi.mocked(api.post)).toHaveBeenCalledWith('/telegram/link-code/')
  })

  it('a linked account sees its username and can unlink', async () => {
    routeGet({ '/telegram/status/': { linked: true, username: 'humo', linked_at: '2030-01-01T00:00:00Z' } })
    vi.mocked(api.delete).mockResolvedValue({ status: 204 })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<SettingsPage />, { path: '/app/settings', url: '/app/settings?tab=telegram' })
    expect(await screen.findByText(/Linked as @humo/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Get link code' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Unlink Telegram' }))
    await vi.waitFor(() => expect(vi.mocked(api.delete)).toHaveBeenCalledWith('/telegram/status/'))
  })

  it('a failed status request shows an error instead of a blank card', async () => {
    vi.mocked(api.get).mockRejectedValue(httpError(500, {}))
    renderApp(<SettingsPage />, { path: '/app/settings', url: '/app/settings?tab=telegram' })
    expect(await screen.findByText('Could not load the Telegram status. Try again later.')).toBeInTheDocument()
  })
})
