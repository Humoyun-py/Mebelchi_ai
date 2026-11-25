import { BASE_INPUT, DEFAULT_COLORS, GROUP_OF_KIND, cleanColors, fromConfig, geometryBody, isValidInput, newDoc, snapshot, toConfig } from './editor'
import { VIEWS, cameraPose } from './editor3d'

describe('editor document', () => {
  it('starts from the same defaults the calculator uses and is valid', () => {
    const d = newDoc()
    expect(d.input).toMatchObject({ width: 800, height: 2000, depth: 400, thickness: 18, shelves: 3, doors: 2, drawers: 0, cabinet_type: 'standard', handle_style: 'bar', edge_thickness: 0 })
    expect(isValidInput(d.input)).toBe(true)
  })

  it('a blank number field (NaN while typing) makes the input invalid, optional fields may be absent', () => {
    expect(isValidInput({ ...BASE_INPUT, width: NaN })).toBe(false)
    expect(isValidInput({ ...BASE_INPUT, edge_thickness: NaN })).toBe(false)
    const { edge_thickness: _e, ...rest } = BASE_INPUT
    expect(isValidInput(rest as typeof BASE_INPUT)).toBe(true)
  })

  it('what is saved loads back to exactly the same document', () => {
    const d = newDoc({ name: 'Kitchen wall', projectId: '7', materialId: '3', colors: { fronts: '#445566', handle: '#AABBCC' }, input: { ...BASE_INPUT, cabinet_type: 'kitchen_wall', depth: 320, handle_style: 'knob', doors: 2, drawers: 0 } })
    const cfg = toConfig(d)
    expect(cfg).toMatchObject({ schema_version: 1, material: 3, colors: { fronts: '#445566', handle: '#aabbcc' } })
    const back = fromConfig(cfg, 'Kitchen wall', 7)
    expect(snapshot(back)).toBe(snapshot(d))
    expect(back.input.cabinet_type).toBe('kitchen_wall')
  })

  it('reads older designs: seven numbers and a single colour', () => {
    const d = fromConfig({ input: { width: 900, height: 1800, depth: 500, thickness: 18, shelves: 2, doors: 2, drawers: 0 }, color: '#8B6F4E' }, 'Old', null)
    expect(d.input).toMatchObject({ width: 900, handle_style: 'bar', cabinet_type: 'standard', back_material: 'HDF' })   // missing fields take defaults
    expect(d.colors).toEqual({ carcass: '#8b6f4e', fronts: '#8b6f4e' })                                                  // the old colour painted carcass and fronts
    expect(d.projectId).toBe(''); expect(d.materialId).toBe('')
    expect(fromConfig(undefined, 'Empty', null).input).toEqual(BASE_INPUT)
  })

  it('the legacy colour field stays readable for old clients (carcass colour or the default)', () => {
    expect(toConfig(newDoc()).color).toBe(DEFAULT_COLORS.carcass)
    expect(toConfig(newDoc({ colors: { carcass: '#112233' } })).color).toBe('#112233')
  })

  it('the geometry request carries the colours; unset groups are not sent', () => {
    expect(geometryBody(newDoc()).colors).toEqual({})
    expect(geometryBody(newDoc({ colors: { fronts: '#ABCDEF' } })).colors).toEqual({ fronts: '#abcdef' })
    expect(cleanColors({ carcass: '', fronts: '#FFF000' })).toEqual({ fronts: '#fff000' })
  })

  it('the snapshot changes with every saved property and nothing else', () => {
    const base = newDoc({ name: 'A' }); const s0 = snapshot(base)
    expect(snapshot({ ...base, name: ' A ' })).toBe(s0)                                   // surrounding spaces do not count as a change
    for (const changed of [{ ...base, name: 'B' }, { ...base, projectId: '2' }, { ...base, materialId: '4' }, { ...base, colors: { back: '#000000' } }, { ...base, input: { ...base.input, width: 801 } },
      { ...base, input: { ...base.input, handle_style: 'none' as const } }]) expect(snapshot(changed)).not.toBe(s0)
  })

  it('colour groups match the server\'s grouping of components', () => {
    expect(GROUP_OF_KIND).toEqual({ carcass: 'carcass', shelf: 'carcass', door: 'fronts', drawer: 'fronts', back: 'back', handle: 'handle' })
  })
})

describe('camera poses', () => {
  const dims = { width: 800, height: 2000, depth: 400 }
  const len = (v: number[]) => Math.hypot(...v)

  it('the 3D view looks at the cabinet from the front-right-above', () => {
    const p = cameraPose('perspective', dims, 1.6)
    expect(p.fov).toBe(38); expect(p.up).toEqual([0, 1, 0]); expect(p.position[0]).toBeGreaterThan(0); expect(p.position[1]).toBeGreaterThan(0); expect(p.position[2]).toBeGreaterThan(p.position[0])
  })

  it('axis views sit on their axis, looking at the centre, with a narrow field of view', () => {
    const f = cameraPose('front', dims, 1.6), s = cameraPose('side', dims, 1.6), t = cameraPose('top', dims, 1.6)
    expect(f.position[0]).toBe(0); expect(f.position[1]).toBe(0); expect(f.position[2]).toBeGreaterThan(0)
    expect(s.position[1]).toBe(0); expect(s.position[2]).toBe(0); expect(s.position[0]).toBeGreaterThan(0)
    expect(t.position[0]).toBe(0); expect(t.position[2]).toBe(0); expect(t.position[1]).toBeGreaterThan(0); expect(t.up).toEqual([0, 0, -1])
    for (const p of [f, s, t]) expect(p.fov).toBeLessThan(10)
  })

  it('the whole cabinet fits the picture in every axis view, whatever the screen shape', () => {
    for (const aspect of [0.5, 1, 1.6, 3]) for (const view of ['front', 'side', 'top'] as const) {
      const p = cameraPose(view, dims, aspect)
      const [ex, ey, along] = view === 'front' ? [0.8, 2.0, 0.4] : view === 'side' ? [0.4, 2.0, 0.8] : [0.8, 0.4, 2.0]
      const halfV = (len(p.position) - along / 2) * Math.tan((p.fov * Math.PI) / 360)     // visible half-height at the cabinet's near face
      expect(halfV, `${view} ${aspect} height`).toBeGreaterThanOrEqual(ey / 2)
      expect(halfV * aspect, `${view} ${aspect} width`).toBeGreaterThanOrEqual(ex / 2)
    }
  })

  it('a bigger cabinet is viewed from further away and every view has a pose', () => {
    expect(len(cameraPose('front', { width: 4000, height: 3000, depth: 1000 }, 1.6).position)).toBeGreaterThan(len(cameraPose('front', dims, 1.6).position))
    expect(VIEWS.every((v) => len(cameraPose(v, dims, 1).position) > 0)).toBe(true)
  })

  it('degenerate screen sizes do not break the maths', () => {
    for (const a of [0, -1, 0.0001]) expect(Number.isFinite(len(cameraPose('front', dims, a).position))).toBe(true)
  })
})
