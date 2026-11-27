import { fireEvent, screen, waitFor } from '@testing-library/react'
import { api } from '../../lib/api'
import type { AndroidRelease } from '../../lib/types'
import { httpError, renderApp, routeGet } from '../../test/utils'
import { useUI } from '../../stores/ui'
import Download from './Download'

vi.mock('../../lib/api', async (orig) => ({ ...(await orig<typeof import('../../lib/api')>()), api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); useUI.setState({ language: 'en' }) })

const rel = (o: Partial<AndroidRelease> = {}): AndroidRelease => ({ version_name: '1.1.0', version_code: 2, sha256: 'a'.repeat(64), size_bytes: 31457280, notes: 'Room designer\n<b>not html</b>', published_at: '2026-11-27T10:00:00Z', download_url: '/api/v1/app/android/2/download/', ...o })
const show = (data: unknown) => { routeGet({ '/app/android/': data }); return renderApp(<Download />) }

describe('Android download page', () => {
  it('offers the newest build with version, size and checksum, straight from the API', async () => {
    show({ latest: rel(), releases: [rel(), rel({ version_name: '1.0.0', version_code: 1, download_url: '/api/v1/app/android/1/download/', size_bytes: 1048576 })] })
    const link = (await screen.findByRole('link', { name: /Download Android app/ })) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/api/v1/app/android/2/download/')
    expect(link).toHaveAttribute('download')
    expect(screen.getByText('1.1.0')).toBeInTheDocument()
    expect(screen.getByText('30.0 MB')).toBeInTheDocument()
    expect(screen.getByTestId('sha').textContent).toBe('a'.repeat(64))
  })

  it('lists older versions with their own links and does not repeat the newest one', async () => {
    show({ latest: rel(), releases: [rel(), rel({ version_name: '1.0.0', version_code: 1, download_url: '/api/v1/app/android/1/download/' })] })
    const old = (await screen.findByRole('link', { name: 'Download 1.0.0' })) as HTMLAnchorElement
    expect(old.getAttribute('href')).toBe('/api/v1/app/android/1/download/')
    expect(screen.queryByRole('link', { name: 'Download 1.1.0' })).not.toBeInTheDocument()
  })

  it('shows release notes as plain text, never as HTML', async () => {
    show({ latest: rel(), releases: [rel()] })
    expect(await screen.findByText(/<b>not html<\/b>/)).toBeInTheDocument()
    expect(document.querySelector('p b')).toBeNull()
  })

  it('is honest when nothing is published: no download button', async () => {
    show({ latest: null, releases: [] })
    expect(await screen.findByText('The Android app is not available yet')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Download/ })).not.toBeInTheDocument()
  })

  it('shows an error with a retry that asks again', async () => {
    routeGet({ '/app/android/': httpError(500, { error: { status: 500, detail: 'x' } }) })
    renderApp(<Download />)
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThanOrEqual(2))
  })

  it('copies the checksum', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    show({ latest: rel(), releases: [rel()] })
    fireEvent.click(await screen.findByRole('button', { name: /Copy/ }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('a'.repeat(64)))
    expect(await screen.findByText('Copied')).toBeInTheDocument()
  })

  it('speaks Uzbek', async () => {
    useUI.setState({ language: 'uz' })
    show({ latest: rel(), releases: [rel()] })
    expect(await screen.findByRole('link', { name: 'Android ilovani yuklab olish' })).toBeInTheDocument()
  })
})
