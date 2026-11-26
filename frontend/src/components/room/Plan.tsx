import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { clampPosition, doorZones, footprint, openingRect, overlapsAny, type RoomConfig, type RoomItem, snap } from '../../lib/room'
import { useT } from '../../lib/i18n'

interface Drag { id: string; dx: number; dz: number; x: number; z: number }
const PAD = 400

/** Top-down plan. Drag a piece, or focus it and use the arrow keys (10 mm, Shift = 100 mm). The new position is sent to the server,
 *  which has the final say: until it answers the piece shows where you dropped it; if it refuses, the plan returns to the saved layout. */
export function Plan({ config, selected, onSelect, onMove, readOnly }: { config: RoomConfig; selected: string | null; onSelect: (id: string | null) => void; onMove: (id: string, x: number, z: number) => void; readOnly?: boolean }) {
  const t = useT(); const svg = useRef<SVGSVGElement>(null); const [drag, setDrag] = useState<Drag | null>(null)
  const { room, openings } = config; const W = room.width, L = room.length
  // what is drawn (the dragged piece at the pointer) vs. what is saved: the handlers must compare against the saved one
  const shown = config.items.map((i) => (drag && drag.id === i.id ? { ...i, x: drag.x, z: drag.z } : i))
  const zones = doorZones(room, openings)

  /** Pointer position in room millimetres. The SVG may be letter-boxed (the plan is height-limited), so the browser's own screen-to-viewBox
   *  matrix is used; the plain ratio below is only the fallback for environments without SVG layout (jsdom). */
  const toMm = (e: PointerEvent) => {
    const el = svg.current; const m = el?.getScreenCTM?.()
    if (el && m && el.createSVGPoint) { const pt = el.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const p = pt.matrixTransform(m.inverse()); return { x: p.x, z: p.y } }
    const r = el?.getBoundingClientRect(); if (!r || !r.width) return { x: 0, z: 0 }
    const k = (W + 2 * PAD) / r.width
    return { x: (e.clientX - r.left) * k - PAD, z: (e.clientY - r.top) * k - PAD }
  }
  const down = (e: PointerEvent, i: RoomItem) => {
    onSelect(i.id); if (readOnly) return
    const p = toMm(e); (e.currentTarget as Element).setPointerCapture?.(e.pointerId)
    setDrag({ id: i.id, dx: p.x - i.x, dz: p.z - i.z, x: i.x, z: i.z })
  }
  const move = (e: PointerEvent, i: RoomItem) => {
    if (!drag || drag.id !== i.id) return
    const p = toMm(e); const c = clampPosition(i, snap(p.x - drag.dx), snap(p.z - drag.dz), room)
    setDrag({ ...drag, x: c.x, z: c.z })
  }
  const up = (i: RoomItem) => { if (drag && drag.id === i.id) { if (drag.x !== i.x || drag.z !== i.z) onMove(i.id, drag.x, drag.z); setDrag(null) } }
  const key = (e: KeyboardEvent, i: RoomItem) => {
    const step = e.shiftKey ? 100 : 10; const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key]
    if (e.key === 'Escape') { onSelect(null); return }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(i.id); return }
    if (!d || readOnly) return
    e.preventDefault(); const c = clampPosition(i, i.x + d[0], i.z + d[1], room); if (c.x !== i.x || c.z !== i.z) onMove(i.id, c.x, c.z)
  }
  const fs = Math.max(W, L) / 40

  return (
    <svg ref={svg} viewBox={`${-PAD} ${-PAD} ${W + 2 * PAD} ${L + 2 * PAD}`} className="mx-auto max-h-[560px] w-full touch-none select-none rounded-[14px] border border-line bg-card2" role="group" aria-label={t('room.planLabel')}
      onPointerDown={(e) => { if (e.target === e.currentTarget) onSelect(null) }}>
      <rect x={0} y={0} width={W} height={L} fill={config.colors.floor} fillOpacity={0.35} stroke="var(--muted)" strokeWidth={40} />
      {zones.map((z, i) => <rect key={`z${i}`} x={z.x0} y={z.z0} width={z.x1 - z.x0} height={z.z1 - z.z0} fill="var(--warning)" fillOpacity={0.12} stroke="var(--warning)" strokeDasharray="60 40" strokeWidth={12} aria-hidden />)}
      {openings.map((o, i) => { const r = openingRect(o, room); return <rect key={`o${i}`} x={r.x0} y={r.z0} width={r.x1 - r.x0} height={r.z1 - r.z0} fill={o.type === 'door' ? 'var(--primary)' : '#22d3ee'} data-opening={o.type}><title>{`${o.type} ${o.width} mm`}</title></rect> })}
      {shown.map((v, n) => {
        const i = config.items[n]; const f = footprint(v); const sel = selected === i.id; const bad = overlapsAny(v, shown)
        const front = { 0: [f.x0, f.z1, f.x1, f.z1], 90: [f.x1, f.z0, f.x1, f.z1], 180: [f.x0, f.z0, f.x1, f.z0], 270: [f.x0, f.z0, f.x0, f.z1] }[i.rot]
        return (
          <g key={i.id} data-item={i.id} role="button" tabIndex={0} aria-pressed={sel} aria-label={`${i.name || i.template}, ${i.width} x ${i.depth} mm, x ${i.x} z ${i.z}`}
            onPointerDown={(e) => down(e, i)} onPointerMove={(e) => move(e, i)} onPointerUp={() => up(i)} onPointerCancel={() => setDrag(null)} onKeyDown={(e) => key(e, i)} onFocus={() => onSelect(i.id)}
            style={{ cursor: readOnly ? 'default' : drag?.id === i.id ? 'grabbing' : 'grab', outline: 'none' }}>
            <rect x={f.x0} y={f.z0} width={f.x1 - f.x0} height={f.z1 - f.z0} fill={i.color || config.colors.item} fillOpacity={0.9} stroke={bad ? 'var(--danger)' : sel ? 'var(--primary)' : 'var(--muted)'} strokeWidth={sel || bad ? 30 : 14} />
            <line x1={front[0]} y1={front[1]} x2={front[2]} y2={front[3]} stroke="var(--fg)" strokeWidth={34} strokeLinecap="round" opacity={0.7} />
            <text x={(f.x0 + f.x1) / 2} y={(f.z0 + f.z1) / 2} textAnchor="middle" dominantBaseline="middle" fontSize={fs} fill="#0f172a" pointerEvents="none">{(i.name || i.template).slice(0, 18)}</text>
          </g>
        )
      })}
      <text x={W / 2} y={-PAD / 2 + fs / 2} textAnchor="middle" fontSize={fs * 1.1} fill="var(--muted)">{(W / 1000).toFixed(1)} m</text>
      <text x={-PAD / 2} y={L / 2} textAnchor="middle" fontSize={fs * 1.1} fill="var(--muted)" transform={`rotate(-90 ${-PAD / 2} ${L / 2})`}>{(L / 1000).toFixed(1)} m</text>
    </svg>
  )
}
