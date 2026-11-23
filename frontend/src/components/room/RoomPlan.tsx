import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import clsx from 'clsx'
import { FRONT, clampPosition, doorZones, footprint, openingRect, overlaps, snap, type Opening, type Room, type RoomItem } from '../../lib/roomFlow'

const PAD = 400

/** Top-down plan: north is up, west is left (x grows east, z grows south). Items are dragged with the pointer or moved
 *  with the arrow keys (100 mm, 500 mm with Shift). The plan only proposes a position; the server decides. */
export function RoomPlan({ room, openings, items, selectedId, onSelect, onMove, disabled, label }: {
  room: Room; openings: Opening[]; items: RoomItem[]; selectedId: string | null; onSelect: (id: string | null) => void
  onMove: (id: string, x: number, z: number) => void; disabled?: boolean; label: (item: RoomItem, n: number) => string
}) {
  const ref = useRef<SVGSVGElement>(null)
  const drag = useRef<{ id: string; dx: number; dz: number; moved: boolean } | null>(null)
  const [ghost, setGhost] = useState<{ id: string; x: number; z: number } | null>(null)
  const vb = { x: -PAD, z: -PAD, w: room.width + PAD * 2, h: room.length + PAD * 2 }
  const zones = doorZones(room, openings)
  const font = Math.max(room.width, room.length) / 45

  const toMm = (e: { clientX: number; clientY: number }) => {
    const r = ref.current!.getBoundingClientRect()
    return { x: vb.x + ((e.clientX - r.left) / r.width) * vb.w, z: vb.z + ((e.clientY - r.top) / r.height) * vb.h }
  }
  const down = (it: RoomItem) => (e: PointerEvent<SVGGElement>) => {
    onSelect(it.id)
    if (disabled) return
    try { e.currentTarget.setPointerCapture?.(e.pointerId) } catch { /* not supported: dragging still works while the pointer stays over the item */ }
    const p = toMm(e)
    drag.current = { id: it.id, dx: p.x - it.x, dz: p.z - it.z, moved: false }
  }
  const move = (it: RoomItem) => (e: PointerEvent<SVGGElement>) => {
    const d = drag.current
    if (!d || d.id !== it.id) return
    const p = toMm(e)
    const next = clampPosition(it, snap(p.x - d.dx), snap(p.z - d.dz), room)
    d.moved = d.moved || next.x !== it.x || next.z !== it.z
    setGhost({ id: it.id, ...next })
  }
  const up = (it: RoomItem) => () => {
    const d = drag.current, g = ghost
    drag.current = null; setGhost(null)
    if (d?.moved && g && g.id === it.id && (g.x !== it.x || g.z !== it.z)) onMove(it.id, g.x, g.z)
  }
  const key = (it: RoomItem) => (e: KeyboardEvent<SVGGElement>) => {
    const step = e.shiftKey ? 500 : 100
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key as 'ArrowLeft']
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(it.id); return }
    if (!delta) return
    e.preventDefault()
    if (disabled) return
    const next = clampPosition(it, it.x + delta[0], it.z + delta[1], room)
    if (next.x !== it.x || next.z !== it.z) onMove(it.id, next.x, next.z)
  }

  return (
    <svg ref={ref} viewBox={`${vb.x} ${vb.z} ${vb.w} ${vb.h}`} style={{ aspectRatio: `${vb.w} / ${vb.h}` }} className="h-auto w-full max-h-[70vh] touch-none select-none rounded-[14px] border border-line bg-card2"
      role="group" aria-label="Room plan" onPointerDown={(e) => { if (e.target === e.currentTarget) onSelect(null) }}>
      <rect x={0} y={0} width={room.width} height={room.length} fill="var(--card)" stroke="var(--muted)" strokeWidth={font * 0.35} />
      {zones.map((z, i) => <rect key={i} data-testid="door-zone" x={z[0]} y={z[1]} width={z[2] - z[0]} height={z[3] - z[1]} fill="none" stroke="var(--warning)" strokeOpacity={0.7} strokeDasharray={`${font} ${font * 0.6}`} strokeWidth={font * 0.2} />)}
      {openings.map((o, i) => { const r = openingRect(o, room); return <line key={o.id ?? i} data-testid={`opening-${o.type}`} x1={r[0]} y1={r[1]} x2={r[2]} y2={r[3]} stroke={o.type === 'door' ? 'var(--warning)' : 'var(--primary)'} strokeWidth={font * 0.9} strokeLinecap="butt" /> })}
      {items.map((it, n) => {
        const at = ghost?.id === it.id ? { ...it, x: ghost.x, z: ghost.z } : it
        const [x0, z0, x1, z1] = footprint(at)
        const blocksDoor = zones.some((z) => overlaps([x0, z0, x1, z1], z))
        const sel = it.id === selectedId
        const [fx, fz] = FRONT[it.rot]
        const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2
        return (
          <g key={it.id} data-testid={`item-${it.id}`} tabIndex={0} role="button" aria-label={label(it, n + 1)} aria-pressed={sel} className={clsx('outline-none', disabled ? 'cursor-default' : 'cursor-grab')}
            onPointerDown={down(it)} onPointerMove={move(it)} onPointerUp={up(it)} onPointerCancel={up(it)} onKeyDown={key(it)} onFocus={() => onSelect(it.id)}>
            <rect x={x0} y={z0} width={x1 - x0} height={z1 - z0} rx={font * 0.2} fill={it.color || 'var(--primary)'} fillOpacity={0.85}
              stroke={sel ? 'var(--primary)' : blocksDoor ? 'var(--warning)' : 'var(--muted)'} strokeWidth={sel ? font * 0.5 : font * 0.25} />
            <line x1={cx} y1={cz} x2={cx + fx * (Math.min(x1 - x0, z1 - z0) / 2)} y2={cz + fz * (Math.min(x1 - x0, z1 - z0) / 2)} stroke="#0f172a" strokeWidth={font * 0.3} strokeLinecap="round" />
            <text x={cx} y={cz} dy={font * 0.35} textAnchor="middle" fontSize={font} fill="#0f172a" fontWeight={600} pointerEvents="none">{n + 1}</text>
          </g>
        )
      })}
      <text x={room.width / 2} y={-PAD / 2.2} textAnchor="middle" fontSize={font} fill="var(--muted)" pointerEvents="none">{room.width} mm</text>
      <text x={room.width + PAD / 2.2} y={room.length / 2} textAnchor="middle" fontSize={font} fill="var(--muted)" transform={`rotate(90 ${room.width + PAD / 2.2} ${room.length / 2})`} pointerEvents="none">{room.length} mm</text>
    </svg>
  )
}
