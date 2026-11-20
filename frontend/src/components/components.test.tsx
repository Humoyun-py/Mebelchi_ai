import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Button } from './ui/Button'
import { Input, NumberField } from './ui/Field'
import { ConfirmDialog } from './ui/Modal'
import { Pagination, Progress } from './ui/Misc'
import { FrontView } from './CabinetPanel'
import { Logo } from './Logo'

describe('ui components', () => {
  it('Button shows a spinner and blocks clicks while loading', () => {
    const fn = vi.fn(); render(<Button loading onClick={fn}>Save</Button>)
    const b = screen.getByRole('button', { name: /save/i }); expect(b).toBeDisabled(); fireEvent.click(b); expect(fn).not.toHaveBeenCalled()
  })
  it('Input associates label and error, toggles password visibility', () => {
    render(<Input label="Password" type="password" error="Too short" />)
    const input = screen.getByLabelText('Password', { selector: 'input' }); expect(input).toHaveAttribute('type', 'password'); expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Too short')
    fireEvent.click(screen.getByRole('button', { name: 'Show password' })); expect(input).toHaveAttribute('type', 'text')
  })
  it('NumberField reports numeric changes and NaN for empty', () => {
    const fn = vi.fn(); render(<NumberField label="Width" value={800} onChange={fn} unit="mm" />)
    const i = screen.getByLabelText('Width'); fireEvent.change(i, { target: { value: '900' } }); expect(fn).toHaveBeenLastCalledWith(900)
    fireEvent.change(i, { target: { value: '' } }); expect(fn.mock.calls.at(-1)![0]).toBeNaN()
  })
  it('ConfirmDialog confirms and cancels', () => {
    const ok = vi.fn(), no = vi.fn(); render(<ConfirmDialog open title="Delete" message="Sure?" onConfirm={ok} onClose={no} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Delete' })); expect(ok).toHaveBeenCalled()
    fireEvent.keyDown(document, { key: 'Escape' }); expect(no).toHaveBeenCalled()
  })
  it('Pagination hides for a single page and navigates', () => {
    const fn = vi.fn(); const { container, rerender } = render(<Pagination page={1} count={10} pageSize={24} onPage={fn} />); expect(container).toBeEmptyDOMElement()
    rerender(<Pagination page={1} count={60} pageSize={24} onPage={fn} />); fireEvent.click(screen.getByLabelText('Next page')); expect(fn).toHaveBeenCalledWith(2)
    expect(screen.getByLabelText('Previous page')).toBeDisabled()
  })
  it('Progress clamps and exposes value', () => {
    render(<Progress value={140} label="Usage" />); expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })
  it('Logo links home', () => { render(<MemoryRouter><Logo /></MemoryRouter>); expect(screen.getByRole('link', { name: /MEBELCHI AI home/ })).toHaveAttribute('href', '/') })
})

describe('FrontView', () => {
  const boxes = [{ name: 'Left side', kind: 'carcass', x: 0, y: 0, z: 0, sx: 18, sy: 2000, sz: 400, color: '#c9a27a' }, { name: 'Door 1', kind: 'door', x: 2, y: 2, z: 400, sx: 396, sy: 1996, sz: 18, color: '#b98f63' }]
  it('renders one rect per component and selects on click', () => {
    const sel = vi.fn(); const { container } = render(<FrontView boxes={boxes} dims={{ width: 800, height: 2000, depth: 400 }} onSelect={sel} />)
    expect(screen.getByRole('img')).toHaveAttribute('aria-label', 'Front view, 800 by 2000 millimetres')
    const rects = container.querySelectorAll('rect'); expect(rects).toHaveLength(2); fireEvent.click(rects[1]); expect(sel).toHaveBeenCalledWith(expect.objectContaining({ name: 'Door 1' }))
  })
})
