import { useMemo, useState } from 'react'
import { Box, Check, Plus, RotateCw, Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { NumberField } from '../ui/Field'
import { Skeleton } from '../ui/Misc'
import { Tabs } from '../ui/Tabs'
import { CabinetViewer } from '../three/LazyViewer'
import { RoomPlan } from './RoomPlan'
import { useRoomModel } from '../../hooks/roomFlow'
import { useL, useT } from '../../lib/i18n'
import { fill, nextRot, warningKey, type FlowView, type RoomItem } from '../../lib/roomFlow'

/** Place, move, rotate and resize furniture. Every change goes to the server, which validates it and returns the
 *  new list; the plan and the 3D view always show what the server holds. */
export function Furnish({ flow, busy, onAdd, onPatch, onRemove, onFinish, finishing }: {
  flow: FlowView; busy: boolean; onAdd: (slug: string) => void; onPatch: (id: string, patch: Partial<RoomItem>) => void; onRemove: (id: string) => void
  onFinish: () => void; finishing: boolean
}) {
  const L = useL(), t = useT()
  const items = flow.items ?? []
  const room = flow.room!
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState<'plan' | '3d'>('plan')
  const item = items.find((i) => i.id === selected) ?? null
  const model = useRoomModel(flow.id, flow.rev, tab === '3d')
  const boxes = useMemo(() => model.data?.boxes.filter((b) => b.kind !== 'ceiling'), [model.data])
  const catalog = flow.descriptor.catalog ?? []
  const nameOf = (i: RoomItem) => i.name || catalog.find((c) => c.slug === i.template)?.name || i.id
  const labelOf = (i: RoomItem, n: number) => fill(t('rf.itemLabel'), { n, name: nameOf(i) })
  const warnings = (flow.warnings ?? []).map((w) => {
    const key = warningKey(w)
    if (!key) return w.message ?? w.code
    const name = w.code === 'not_placed' ? L(catalog.find((c) => c.slug === w.item)?.label) || w.item : nameOf(items.find((i) => i.id === w.item) ?? ({ id: '' } as RoomItem))
    return fill(t(key), { name: name ?? '' })
  })
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
      <div className="min-w-0 space-y-3">
        <Tabs tabs={[{ id: 'plan', label: t('rf.plan'), icon: <Box size={15} /> }, { id: '3d', label: t('rf.view3d'), icon: <Box size={15} /> }]} value={tab} onChange={setTab} />
        {tab === 'plan' ? (
          <>
            <RoomPlan room={room} openings={flow.openings ?? []} items={items} selectedId={selected} onSelect={setSelected} disabled={busy} label={labelOf}
              onMove={(id, x, z) => onPatch(id, { x, z })} />
            <p className="text-xs text-muted">{t('rf.hint')}</p>
          </>
        ) : boxes && model.data ? <CabinetViewer boxes={boxes} dims={{ width: model.data.dimensions.width, height: model.data.dimensions.height, depth: model.data.dimensions.length }} showDims={false} className="h-[min(65vh,520px)]" />
          : <Skeleton className="h-[420px]" />}
        {warnings.length > 0 && <ul className="space-y-1" aria-label="Warnings">{warnings.map((w, i) => <li key={i} role="status" className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">{w}</li>)}</ul>}
        <p className="text-xs text-muted">{t('rf.disclaimer')}</p>
      </div>
      <div className="space-y-4">
        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">{t('rf.catalog')}</h3>
          <div className="flex flex-wrap gap-2">{catalog.map((c) => <Button key={c.slug} size="sm" variant="secondary" icon={<Plus size={14} />} disabled={busy} onClick={() => onAdd(c.slug)}>{L(c.label)}</Button>)}</div>
        </Card>
        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">{t('rf.selected')}</h3>
          {item ? (
            <ItemEditor key={`${item.id}:${item.x}:${item.z}:${item.width}:${item.depth}:${item.height}:${item.rot}`} item={item} name={nameOf(item)} busy={busy} onPatch={onPatch}
              onRemove={(id) => { onRemove(id); setSelected(null) }} />
          ) : <p className="text-sm text-muted">{t('rf.pickItem')}</p>}
        </Card>
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-semibold">{t('rf.items')}</h3>
          {items.length ? <ol className="space-y-1 text-sm">{items.map((i, n) => (
            <li key={i.id}><button type="button" onClick={() => setSelected(i.id)} aria-pressed={i.id === selected} className={`w-full rounded-md px-2 py-1 text-left hover:bg-card2 ${i.id === selected ? 'bg-primary/10' : ''}`}>{n + 1}. {nameOf(i)}</button></li>))}</ol>
            : <p className="text-sm text-muted">{t('rf.noItems')}</p>}
        </Card>
        <Button className="w-full" loading={finishing} onClick={onFinish}>{t('rf.finish')}</Button>
      </div>
    </div>
  )
}

/** The draft starts from the server's values and is rebuilt (by `key`) whenever the server's values change, so it never drifts. */
function ItemEditor({ item, name, busy, onPatch, onRemove }: { item: RoomItem; name: string; busy: boolean; onPatch: (id: string, patch: Partial<RoomItem>) => void; onRemove: (id: string) => void }) {
  const t = useT()
  const [draft, setDraft] = useState({ x: item.x, z: item.z, width: item.width, depth: item.depth, height: item.height })
  const dirty = draft.x !== item.x || draft.z !== item.z || draft.width !== item.width || draft.depth !== item.depth || draft.height !== item.height
  const valid = Object.values(draft).every(Number.isFinite)
  return (
    <>
      <p className="text-sm text-muted">{name}</p>
      <div className="grid grid-cols-2 gap-3">
        <NumberField label={t('rf.width')} value={draft.width} onChange={(n) => setDraft({ ...draft, width: n })} />
        <NumberField label={t('rf.depth')} value={draft.depth} onChange={(n) => setDraft({ ...draft, depth: n })} />
        <NumberField label={t('rf.height')} value={draft.height} onChange={(n) => setDraft({ ...draft, height: n })} />
        <span />
        <NumberField label="x (mm)" value={draft.x} onChange={(n) => setDraft({ ...draft, x: n })} />
        <NumberField label="z (mm)" value={draft.z} onChange={(n) => setDraft({ ...draft, z: n })} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" icon={<Check size={14} />} disabled={busy || !dirty || !valid} onClick={() => onPatch(item.id, draft)}>{t('rf.apply')}</Button>
        <Button size="sm" variant="secondary" icon={<RotateCw size={14} />} disabled={busy} onClick={() => onPatch(item.id, { rot: nextRot(item.rot) })}>{t('rf.rotate')}</Button>
        <Button size="sm" variant="danger" icon={<Trash2 size={14} />} disabled={busy} onClick={() => onRemove(item.id)}>{t('rf.remove')}</Button>
      </div>
    </>
  )
}
