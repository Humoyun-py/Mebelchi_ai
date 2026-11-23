import { CEILING_MARGIN, clampPosition, defaultOpening, doorZones, fill, footprint, nextRot, openingRect, overlaps, snap, warningKey, type Opening, type Room } from './roomFlow'

const room: Room = { width: 4000, length: 3000, height: 2700 }
const item = { rot: 0 as const, width: 800, depth: 400 }

describe('footprint', () => {
  // The same cases as backend/apps/geometry/tests/test_room.py, so plan and server agree on the footprint.
  it('swaps width and depth on a quarter turn', () => {
    expect(footprint({ ...item, x: 100, z: 0 })).toEqual([100, 0, 900, 400])
    expect(footprint({ ...item, rot: 90, x: 0, z: 0 })).toEqual([0, 0, 400, 800])
    expect(footprint({ ...item, rot: 180, x: 0, z: 0 })).toEqual([0, 0, 800, 400])
    expect(footprint({ ...item, rot: 270, x: 0, z: 0 })).toEqual([0, 0, 400, 800])
  })
  it('touching rectangles do not overlap, crossing ones do', () => {
    expect(overlaps([0, 0, 800, 400], [800, 0, 1600, 400])).toBe(false)
    expect(overlaps([0, 0, 800, 400], [0, 400, 800, 800])).toBe(false)
    expect(overlaps([0, 0, 800, 400], [700, 100, 1500, 500])).toBe(true)
  })
})

describe('clampPosition', () => {
  it('keeps the footprint inside the room', () => {
    expect(clampPosition(item, -50, -10, room)).toEqual({ x: 0, z: 0 })
    expect(clampPosition(item, 9999, 9999, room)).toEqual({ x: 3200, z: 2600 })
    expect(clampPosition({ ...item, rot: 90 }, 9999, 9999, room)).toEqual({ x: 3600, z: 2200 })   // rotated: 400 x 800
    expect(clampPosition(item, 1000, 500, room)).toEqual({ x: 1000, z: 500 })
  })
  it('never returns a negative position for an item larger than the room', () => {
    expect(clampPosition({ rot: 0, width: 5000, depth: 400 }, 100, 0, room)).toEqual({ x: 0, z: 0 })
  })
})

describe('snap, rotation, text', () => {
  it('snaps to 50 mm', () => { expect([snap(24), snap(26), snap(74), snap(76)]).toEqual([0, 50, 50, 100]) })
  it('rotates through the four orientations', () => { expect([0, 90, 180, 270].map((r) => nextRot(r as 0))).toEqual([90, 180, 270, 0]) })
  it('fills placeholders and leaves unknown ones empty', () => { expect(fill('Step {i} of {n} {x}', { i: 2, n: 7 })).toBe('Step 2 of 7 ') })
  it('maps server warning codes to text keys', () => {
    expect(warningKey({ code: 'door_zone' })).toBe('rf.warnDoor')
    expect(warningKey({ code: 'not_placed' })).toBe('rf.warnNotPlaced')
    expect(warningKey({ code: 'items_reset' })).toBe('rf.warnReset')
    expect(warningKey({ code: 'something_new' })).toBeNull()
  })
})

describe('openings', () => {
  const door: Opening = { type: 'door', wall: 'north', offset: 1000, width: 900, height: 2100, sill: 0 }
  it('draws an opening on its wall line', () => {
    expect(openingRect(door, room)).toEqual([1000, 0, 1900, 0])
    expect(openingRect({ ...door, wall: 'south' }, room)).toEqual([1000, 3000, 1900, 3000])
    expect(openingRect({ ...door, wall: 'west' }, room)).toEqual([0, 1000, 0, 1900])
    expect(openingRect({ ...door, wall: 'east' }, room)).toEqual([4000, 1000, 4000, 1900])
  })
  it('door zones are 800 mm deep, only for doors', () => {
    const window: Opening = { ...door, type: 'window', wall: 'east', sill: 900 }
    expect(doorZones(room, [door, window])).toEqual([[1000, 0, 1900, 800]])
    expect(doorZones(room, [{ ...door, wall: 'south' }])).toEqual([[1000, 2200, 1900, 3000]])
    expect(doorZones(room, [{ ...door, wall: 'west' }])).toEqual([[0, 1000, 800, 1900]])
    expect(doorZones(room, [{ ...door, wall: 'east' }])).toEqual([[3200, 1000, 4000, 1900]])
  })
  it('defaults stay clear of the ceiling, even in a low room', () => {
    for (const height of [2000, 2300, 2700, 4500]) {
      const r = { ...room, height }
      const d = defaultOpening('door', 'north', r), w = defaultOpening('window', 'east', r)
      expect(d.sill + d.height).toBeLessThanOrEqual(height - CEILING_MARGIN)
      expect(w.sill + w.height).toBeLessThanOrEqual(height - CEILING_MARGIN)
      expect(d.height).toBeGreaterThanOrEqual(1800)
      expect(w.height).toBeGreaterThanOrEqual(300)
    }
    expect(defaultOpening('door', 'north', room)).toMatchObject({ width: 900, height: 2100, sill: 0, offset: 100 })
  })
})
