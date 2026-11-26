import { clampPosition, defaultOpenings, doorZones, footprint, nextRotation, openingRect, overlaps, overlapsAny, snap, wallLength, type RoomItem, type RoomOpening } from './room'

const room = { width: 4000, length: 3000, height: 2700 }
const item = (o: Partial<RoomItem> = {}): RoomItem => ({ id: 'a', template: 'bedside', name: 'Bedside', x: 0, z: 0, rot: 0, width: 450, depth: 400, height: 500, shelves: 0, doors: 0, drawers: 2, color: '', ...o })

describe('room geometry helpers', () => {
  it('swaps width and depth in the footprint for quarter turns', () => {
    expect(footprint(item({ x: 100, z: 200 }))).toEqual({ x0: 100, z0: 200, x1: 550, z1: 600 })
    expect(footprint(item({ x: 100, z: 200, rot: 90 }))).toEqual({ x0: 100, z0: 200, x1: 500, z1: 650 })
    expect(footprint(item({ rot: 180 }))).toEqual(footprint(item({ rot: 0 })))
    expect(footprint(item({ rot: 270 }))).toEqual(footprint(item({ rot: 90 })))
  })
  it('treats touching rectangles as not overlapping', () => {
    expect(overlaps({ x0: 0, z0: 0, x1: 100, z1: 100 }, { x0: 100, z0: 0, x1: 200, z1: 100 })).toBe(false)
    expect(overlaps({ x0: 0, z0: 0, x1: 100, z1: 100 }, { x0: 99, z0: 99, x1: 200, z1: 200 })).toBe(true)
  })
  it('never lets a piece leave the room, whatever its rotation', () => {
    expect(clampPosition(item(), -50, -50, room)).toEqual({ x: 0, z: 0 })
    expect(clampPosition(item(), 9999, 9999, room)).toEqual({ x: 4000 - 450, z: 3000 - 400 })
    expect(clampPosition(item({ rot: 90 }), 9999, 9999, room)).toEqual({ x: 4000 - 400, z: 3000 - 450 })
  })
  it('snaps to 10 mm and finds collisions with other pieces only', () => {
    expect(snap(1234)).toBe(1230); expect(snap(1235)).toBe(1240)
    const a = item({ id: 'a' }), b = item({ id: 'b', x: 200 }), c = item({ id: 'c', x: 2000 })
    expect(overlapsAny(a, [a, b, c])).toBe(true)
    expect(overlapsAny(a, [a, c])).toBe(false)
  })
  it('places door zones and opening bars on the right wall', () => {
    const door: RoomOpening = { type: 'door', wall: 'north', offset: 1000, width: 900, height: 2100, sill: 0 }
    expect(doorZones(room, [door, { ...door, type: 'window' }])).toEqual([{ x0: 1000, z0: 0, x1: 1900, z1: 800 }])
    expect(doorZones(room, [{ ...door, wall: 'east' }])[0]).toEqual({ x0: 3200, z0: 1000, x1: 4000, z1: 1900 })
    expect(openingRect({ ...door, wall: 'south' }, room)).toEqual({ x0: 1000, z0: 2940, x1: 1900, z1: 3060 })
  })
  it('rotates through the four quarter turns and measures walls', () => {
    expect([0, 90, 180, 270].map((r) => nextRotation(r as 0))).toEqual([90, 180, 270, 0])
    expect([wallLength(room, 'north'), wallLength(room, 'east')]).toEqual([4000, 3000])
  })
  it('offers starting openings that fit the walls they sit on', () => {
    const ops = defaultOpenings({ doors: 2, windows: 3 }, room)
    expect(ops.filter((o) => o.type === 'door')).toHaveLength(2); expect(ops.filter((o) => o.type === 'window')).toHaveLength(3)
    for (const o of ops) expect(o.offset + o.width).toBeLessThanOrEqual(wallLength(room, o.wall))
  })
})

describe('3D cutaway', () => {
  it('hides the ceiling and the two front walls but keeps floor, back walls and furniture', async () => {
    const { cutawayBoxes } = await import('./room')
    const box = (name: string, kind: string) => ({ name, kind, x: 0, y: 0, z: 0, sx: 1, sy: 1, sz: 1, color: '#fff' })
    const all = [box('Ceiling', 'ceiling'), box('Floor', 'floor'), box('Wall north', 'wall'), box('Wall west', 'wall'), box('Wall south', 'wall'), box('Wall east', 'wall'), box('Wall east (left of window)', 'wall'), box('Left side', 'panel')]
    expect(cutawayBoxes(all).map((b) => b.name)).toEqual(['Floor', 'Wall north', 'Wall west', 'Left side'])
  })
})
