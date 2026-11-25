import { act, fireEvent, render, screen } from '@testing-library/react'
import { Modal } from './Modal'

describe('Modal focus', () => {
  it('focuses the first field when it opens', async () => {
    render(<Modal open onClose={() => {}} title="Form"><input aria-label="first" /><input aria-label="second" /></Modal>)
    await act(() => new Promise((r) => setTimeout(r, 90)))
    expect(screen.getByLabelText('first')).toHaveFocus()
  })

  it('does not steal focus from a field the user has already moved to (typed text must not land in the wrong field)', async () => {
    render(<Modal open onClose={() => {}} title="Form"><input aria-label="first" /><input aria-label="second" /></Modal>)
    screen.getByLabelText('second').focus()                       // the user clicked the second field right away
    await act(() => new Promise((r) => setTimeout(r, 90)))        // the delayed autofocus fires now
    expect(screen.getByLabelText('second')).toHaveFocus()
    fireEvent.change(screen.getByLabelText('second'), { target: { value: '5000000' } })
    expect(screen.getByLabelText('first')).toHaveValue('')
  })

  it('a closed dialog renders nothing and cleans up its scroll lock', () => {
    const { rerender } = render(<Modal open onClose={() => {}} title="Form"><p>body</p></Modal>)
    expect(document.body.style.overflow).toBe('hidden')
    rerender(<Modal open={false} onClose={() => {}} title="Form"><p>body</p></Modal>)
    expect(document.body.style.overflow).toBe('')
  })
})
