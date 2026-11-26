import { useMemo, useState } from 'react'
import { AlertTriangle, Check, Plus, RotateCw, Shuffle, Trash2 } from 'lucide-react'
import { apiError } from '../../lib/api'
import { cutawayBoxes, nextRotation, type RoomFlow, type RoomItem } from '../../lib/room'
import { useAddItem, useFinish, usePatchItem, useRemoveItem, useResetLayout, useRoomModel } from '../../hooks/rooms'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { NumberField, Select, Switch } from '../ui/Field'
import { ConfirmDialog } from '../ui/Modal'
import { Skeleton } from '../ui/Misc'
import { Tabs } from '../ui/Tabs'
import { toast } from '../ui/Toast'
import { CabinetViewer } from '../three/LazyViewer'
import { Plan } from './Plan'
import { useL, useT } from '../../lib/i18n'

type View = 'plan' | '3d'

function ItemPanel({ item, onApply, onRotate, onRemove, busy, errors }: { item: RoomItem; onApply: (b: Partial<RoomItem>) => void; onRotate: () => void; onRemove: () => void; busy: boolean; errors: Record<string, string> }) {
  const t = useT(); const [d, setD] = useState({ x: item.x, z: item.z, width: item.width, depth: item.depth, height: item.height })
  const dirty = (Object.keys(d) as (keyof typeof d)[]).some((k) => d[k] !== item[k])
  const f = (k: keyof typeof d, label: string) => <NumberField label={label} value={d[k]} onChange={(n) => setD({ ...d, [k]: n })} unit="mm" min={0} step={10} error={errors[k]} />
  return (
    <div className="space-y-3" data-testid="item-panel">
      <h3 className="font-semibold">{item.name || item.template}</h3>
      <div className="grid grid-cols-2 gap-3">{f('x', t('room.x'))}{f('z', t('room.z'))}{f('width', t('room.width'))}{f('depth', t('room.depth'))}{f('height', t('room.height'))}</div>
      {errors.position && <p role="alert" className="text-xs text-danger">{errors.position}</p>}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => onApply(d)} disabled={!dirty} loading={busy}>{t('room.apply')}</Button>
        <Button size="sm" variant="secondary" icon={<RotateCw size={14} />} onClick={onRotate} disabled={busy}>{t('room.rotate')} ({item.rot}°)</Button>
        <Button size="sm" variant="danger" icon={<Trash2 size={14} />} onClick={onRemove} disabled={busy}>{t('room.remove')}</Button>
      </div>
    </div>
  )
}

/** The furnish step: plan or 3D view on the left, furniture catalogue, the selected piece and the warnings on the right. */
export function Workspace({ flow, readOnly }: { flow: RoomFlow; readOnly?: boolean }) {
  const t = useT(); const L = useL(); const id = flow.id; const cfg = flow.room!.config
  const [view, setView] = useState<View>('plan'); const [sel, setSel] = useState<string | null>(null); const [add, setAdd] = useState(''); const [reset, setReset] = useState(false)
  const [errs, setErrs] = useState<Record<string, string>>({}); const [cut, setCut] = useState(true)
  const addItem = useAddItem(id), patch = usePatchItem(id), remove = useRemoveItem(id), resetLayout = useResetLayout(id), finish = useFinish(id)
  const model = useRoomModel(id, view === '3d', flow.updated_at)
  const item = cfg.items.find((i) => i.id === sel) ?? null
  const catalog = flow.question.catalog ?? []
  const names = useMemo(() => Object.fromEntries(cfg.items.map((i) => [i.id, i.name || i.template])), [cfg.items])
  const fail = (e: unknown) => { const m = apiError(e); setErrs(m.fields); toast.error(m.message) }
  const move = (iid: string, x: number, z: number) => { setErrs({}); patch.mutate({ item: iid, body: { x, z } }, { onError: fail }) }
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs tabs={[{ id: 'plan' as View, label: t('room.tab.plan') }, { id: '3d' as View, label: t('room.tab.3d') }]} value={view} onChange={setView} />
          {!readOnly && <p className="text-xs text-muted">{t('room.hintPlan')}</p>}
        </div>
        {view === 'plan' ? <Plan config={cfg} selected={sel} onSelect={setSel} onMove={move} readOnly={readOnly} />
          : model.isLoading || !model.data ? <Skeleton className="h-[480px]" />
          : <div className="space-y-2"><div className="flex items-center gap-2 text-sm"><Switch checked={cut} onChange={setCut} label={t('room.cutaway')} /><span className="text-muted">{t('room.cutaway')}</span></div>
            <CabinetViewer boxes={cut ? cutawayBoxes(model.data.boxes) : model.data.boxes} dims={{ width: model.data.dimensions.width, height: model.data.dimensions.height, depth: model.data.dimensions.depth }} showDims={false} className="h-[480px]" /></div>}
      </div>
      <div className="space-y-4">
        {!readOnly && (
          <Card className="space-y-3 p-4">
            <h3 className="font-semibold">{t('room.add')}</h3>
            <Select label={t('room.template')} value={add} onChange={(e) => setAdd(e.target.value)} options={[{ value: '', label: '—' }, ...catalog.map((c) => ({ value: c.slug, label: L(c.label) }))]} />
            <Button size="sm" icon={<Plus size={14} />} disabled={!add || cfg.items.length >= (flow.question.max_items ?? 60)} loading={addItem.isPending}
              onClick={() => addItem.mutate({ template: add }, { onSuccess: (f) => { setSel(f.item?.id ?? null); setErrs({}) }, onError: fail })}>{t('room.addBtn')}</Button>
          </Card>
        )}
        <Card className="p-4">
          {item ? <ItemPanel key={`${item.id}:${item.x}:${item.z}:${item.width}:${item.depth}:${item.height}`} item={item} busy={patch.isPending || remove.isPending} errors={errs}
              onApply={(b) => { setErrs({}); patch.mutate({ item: item.id, body: b }, { onError: fail }) }}
              onRotate={() => { setErrs({}); patch.mutate({ item: item.id, body: { rot: nextRotation(item.rot) } }, { onError: fail }) }}
              onRemove={() => remove.mutate(item.id, { onSuccess: () => setSel(null), onError: fail })} />
            : <p className="text-sm text-muted">{cfg.items.length ? t('room.pick') : t('room.itemsEmpty')}</p>}
        </Card>
        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-2 font-semibold"><AlertTriangle size={15} aria-hidden />{t('room.warnings')}</h3>
          {flow.room!.warnings.length ? (
            <ul className="space-y-1.5 text-sm" aria-label={t('room.warnings')}>
              {flow.room!.warnings.map((w, i) => <li key={i} className="text-warning">{w.item && names[w.item] ? `${names[w.item]}: ` : ''}{w.message}</li>)}
            </ul>) : <p className="text-sm text-muted">{t('room.noWarnings')}</p>}
        </Card>
        {!readOnly && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<Shuffle size={15} />} onClick={() => setReset(true)} disabled={resetLayout.isPending}>{t('room.reset')}</Button>
            <Button icon={<Check size={15} />} loading={finish.isPending} onClick={() => finish.mutate(undefined, { onSuccess: () => toast.success(t('room.finished')), onError: fail })}>{t('room.finish')}</Button>
          </div>
        )}
      </div>
      <ConfirmDialog open={reset} onClose={() => setReset(false)} title={t('room.resetTitle')} message={t('room.resetMsg')} confirmLabel={t('room.reset')} cancelLabel={t('common.cancel')} loading={resetLayout.isPending}
        onConfirm={() => resetLayout.mutate(undefined, { onSuccess: () => { setReset(false); setSel(null) }, onError: (e) => { setReset(false); fail(e) } })} />
    </div>
  )
}
