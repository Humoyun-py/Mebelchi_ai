import { fireEvent, render, screen } from '@testing-library/react'
import { RoomPlan } from './RoomPlan'
import type { Opening, RoomItem } from '../../lib/roomFlow'

// jsdom has no PointerEvent: MouseEvent carries clientX/clientY, which is all the plan reads.
if (!('PointerEvent' in window)) (window as unknown as { PointerEvent: typeof MouseEvent }).PointerEvent = MouseEvent

const room = { width: 4000, length: 3000, height: 2700 }
const door: Opening = { id: 'd1', type: 'door', wall: 'north', offset: 1000, width: 900, height: 2100, sill: 0 }
const win: Opening = { id: 'w1', type: 'window', wall: 'east', offset: 800, width: 1200, height: 1200, sill: 900 }
const mk = (id: string, x: number, z: number, extra: Partial<RoomItem> = {}): RoomItem => ({ id, template: '', name: id, x, z, rot: 0, width: 800, depth: 400, height: 2000, shelves: 0, doors: 0, drawers: 0, color: '', ...extra })
const label = (i: RoomItem, n: number) => `Item ${n}: ${i.name}`

function setup(items: RoomItem[], over: Partial<Parameters<typeof RoomPlan>[0]> = {}) {
  const onMove = vi.fn(), onSelect = vi.fn()
  const view = render(<RoomPlan room={room} openings={[door, win]} items={items} selectedId={null} onSelect={onSelect} onMove={onMove} label={label} {...over} />)
  const svg = view.container.querySelector('svg')!
  // map client pixels 1:1 onto plan millimetres: viewBox is -400..4400 x -400..3400
  svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 4800, height: 3800, right: 4800, bottom: 3800, x: 0, y: 0, toJSON: () => ({}) })
  return { onMove, onSelect, svg, ...view }
}
const at = (x: number, z: number) => ({ clientX: x + 400, clientY: z + 400, pointerId: 1 })

describe('RoomPlan', () => {
  it('draws the room, its openings, the door zone and every item', () => {
    setup([mk('a', 0, 0), mk('b', 1000, 1000)])
    expect(screen.getAllByTestId('opening-door')).toHaveLength(1)
    expect(screen.getAllByTestId('opening-window')).toHaveLength(1)
    expect(screen.getAllByTestId('door-zone')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Item 1: a' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Item 2: b' })).toBeInTheDocument()
  })

  it('marks an item that blocks a door zone', () => {
    setup([mk('blocker', 1000, 0), mk('fine', 2500, 1500)])
    expect(screen.getByTestId('item-blocker').querySelector('rect')).toHaveAttribute('stroke', 'var(--warning)')
    expect(screen.getByTestId('item-fine').querySelector('rect')).toHaveAttribute('stroke', 'var(--muted)')
  })

  it('selects on click and clears the selection on the background', () => {
    const { onSelect, svg } = setup([mk('a', 0, 0)])
    fireEvent.pointerDown(screen.getByTestId('item-a'), at(100, 100))
    expect(onSelect).toHaveBeenLastCalledWith('a')
    fireEvent.pointerDown(svg, at(2000, 2000))
    expect(onSelect).toHaveBeenLastCalledWith(null)
  })

  it('moves the focused item with the arrow keys, clamped to the room', () => {
    const { onMove } = setup([mk('a', 50, 0)])
    const el = screen.getByTestId('item-a')
    fireEvent.keyDown(el, { key: 'ArrowRight' }); expect(onMove).toHaveBeenLastCalledWith('a', 150, 0)
    fireEvent.keyDown(el, { key: 'ArrowDown' }); expect(onMove).toHaveBeenLastCalledWith('a', 50, 100)
    fireEvent.keyDown(el, { key: 'ArrowRight', shiftKey: true }); expect(onMove).toHaveBeenLastCalledWith('a', 550, 0)
    fireEvent.keyDown(el, { key: 'ArrowLeft' }); expect(onMove).toHaveBeenLastCalledWith('a', 0, 0)       // 50 - 100 clamps to the wall
    onMove.mockClear()
    fireEvent.keyDown(el, { key: 'ArrowUp' }); expect(onMove).not.toHaveBeenCalled()                      // already against the north wall
  })

  it('does not move anything while disabled', () => {
    const { onMove } = setup([mk('a', 500, 500)], { disabled: true })
    fireEvent.keyDown(screen.getByTestId('item-a'), { key: 'ArrowRight' })
    const el = screen.getByTestId('item-a')
    fireEvent.pointerDown(el, at(600, 600)); fireEvent.pointerMove(el, at(1600, 600)); fireEvent.pointerUp(el, at(1600, 600))
    expect(onMove).not.toHaveBeenCalled()
  })

  it('drags an item and commits one move on release, snapped to 50 mm', () => {
    const { onMove } = setup([mk('a', 500, 500)])
    const el = screen.getByTestId('item-a')
    fireEvent.pointerDown(el, at(600, 600))              // grab 100 mm inside the item
    fireEvent.pointerMove(el, at(1237, 900))
    expect(onMove).not.toHaveBeenCalled()                // nothing is sent while dragging
    fireEvent.pointerUp(el, at(1237, 900))
    expect(onMove).toHaveBeenCalledTimes(1)
    expect(onMove).toHaveBeenCalledWith('a', 1150, 800)  // (1237-100, 900-100) snapped
  })

  it('cannot be dragged outside the room', () => {
    const { onMove } = setup([mk('a', 500, 500)])
    const el = screen.getByTestId('item-a')
    fireEvent.pointerDown(el, at(600, 600)); fireEvent.pointerMove(el, at(9000, -900)); fireEvent.pointerUp(el, at(9000, -900))
    expect(onMove).toHaveBeenCalledWith('a', 3200, 0)
  })

  it('a click without movement is not a move', () => {
    const { onMove } = setup([mk('a', 500, 500)])
    const el = screen.getByTestId('item-a')
    fireEvent.pointerDown(el, at(600, 600)); fireEvent.pointerUp(el, at(600, 600))
    expect(onMove).not.toHaveBeenCalled()
  })

  it('draws a rotated item with swapped sides', () => {
    setup([mk('a', 0, 0, { rot: 90 })])
    const r = screen.getByTestId('item-a').querySelector('rect')!
    expect([r.getAttribute('width'), r.getAttribute('height')]).toEqual(['400', '800'])
  })
})
