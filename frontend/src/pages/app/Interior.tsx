import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ImagePlus, Save } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError } from '../../lib/api'
import type { CabinetInput, Design, GalleryImage, Page, Template } from '../../lib/types'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, NumberField, Select, Textarea } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { FileUploader } from '../../components/ui/FileUploader'
import { Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { CabinetViewer } from '../../components/three/LazyViewer'
import { Swatches } from '../../components/CabinetPanel'
import { useGeometry, useMeta, useTemplates } from '../../hooks/queries'
import { useL } from '../../lib/i18n'
import { PanelSection, RightPanel } from '../../layouts/RightPanel'

type Wall = 'north' | 'south' | 'east' | 'west'; type Align = 'start' | 'center' | 'end'
interface Cfg { room: string; style: string; template: string; input: CabinetInput; color: string; wallColor: string; roomW: number; roomL: number; roomH: number; wall: Wall; align: Align; notes: string }
const base: Cfg = { room: 'living', style: 'modern', template: '', input: { width: 1800, height: 450, depth: 400, thickness: 18, shelves: 1, doors: 2, drawers: 0 }, color: '#e5e7eb', wallColor: '#cbd5e1', roomW: 4200, roomL: 5000, roomH: 2700, wall: 'north', align: 'center', notes: '' }

function Plan({ c }: { c: Cfg }) {
  const { roomW: W, roomL: L } = c; const f = c.input; const pad = 300
  const horiz = c.wall === 'north' || c.wall === 'south'
  const fw = horiz ? f.width : f.depth, fh = horiz ? f.depth : f.width
  const span = horiz ? W - fw : L - fh
  const off = c.align === 'start' ? 0 : c.align === 'end' ? span : span / 2
  const x = c.wall === 'west' ? 0 : c.wall === 'east' ? W - fw : off
  const y = c.wall === 'north' ? 0 : c.wall === 'south' ? L - fh : off
  const bad = fw > (horiz ? W : L) || fh > (horiz ? L : W)
  return (
    <svg viewBox={`${-pad} ${-pad} ${W + pad * 2} ${L + pad * 2}`} className="mx-auto max-h-[420px] w-full" role="img" aria-label="Top-down room plan">
      <rect x={0} y={0} width={W} height={L} fill={c.wallColor} fillOpacity={0.25} stroke="var(--muted)" strokeWidth={30} />
      <rect x={Math.max(0, x)} y={Math.max(0, y)} width={fw} height={fh} fill={c.color} stroke={bad ? 'var(--danger)' : 'var(--primary)'} strokeWidth={22} />
      <text x={W / 2} y={L / 2} textAnchor="middle" fill="var(--muted)" fontSize={Math.max(W, L) / 22} fontFamily="Geist Variable, sans-serif">{(W / 1000).toFixed(1)} x {(L / 1000).toFixed(1)} m</text>
    </svg>
  )
}

export default function Interior() {
  const L = useL(); const meta = useMeta(); const ROOMS = meta.data?.rooms ?? []; const STYLES = Object.fromEntries((meta.data?.styles ?? []).map((x) => [x.id, x]))
  const [params] = useSearchParams(); const qc = useQueryClient(); const roomParam = params.get('room'); const styleParam = params.get('style'); const designParam = params.get('design')
  const [c, setC] = useState<Cfg>({ ...base, room: roomParam ?? base.room })
  const [name, setName] = useState('My interior'); const [designId, setDesignId] = useState<number | null>(null); const [imgId, setImgId] = useState<number | null>(null); const [picker, setPicker] = useState(false)
  const all = useTemplates(); const imgs = useQuery({ queryKey: ['gallery', 'room'], queryFn: async () => (await api.get<Page<GalleryImage>>('/gallery/', { params: { source: 'room', page_size: 48 } })).data })
  const room = ROOMS.find((r) => r.id === c.room); const options = useMemo(() => (all.data ?? []).filter((t: Template) => room?.categories.includes(t.category)), [all.data, room])
  useEffect(() => { const sty = styleParam ? STYLES[styleParam] : null; if (sty) setC((x) => ({ ...x, style: sty.id, color: sty.furniture, wallColor: sty.wall })) // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleParam, meta.data])
  const geo = useGeometry(c.input, c.color); const img = imgs.data?.results.find((i) => i.id === imgId)
  const design = useQuery({ queryKey: ['design', designParam], enabled: !!designParam, queryFn: async () => (await api.get<Design>(`/designs/${designParam}/`)).data })
  useEffect(() => { const d = design.data; if (d) { setC({ ...base, ...(d.config as Partial<Cfg>) }); setName(d.name); setDesignId(d.id); setImgId(d.room_image) } }, [design.data])
  const set = <K extends keyof Cfg>(k: K, v: Cfg[K]) => setC((x) => ({ ...x, [k]: v }))
  const style = (id: string) => { const sty = STYLES[id]; if (sty) setC((x) => ({ ...x, style: id, color: sty.furniture, wallColor: sty.wall })) }
  const save = useMutation({
    mutationFn: async () => { const body = { name: name.trim() || 'My interior', kind: 'interior', config: c, room_image: imgId }; return designId ? (await api.patch<Design>(`/designs/${designId}/`, body)).data : (await api.post<Design>('/designs/', body)).data },
    onSuccess: (d) => { setDesignId(d.id); toast.success('Design saved'); qc.invalidateQueries({ queryKey: ['designs'] }); qc.invalidateQueries({ queryKey: ['summary'] }) }, onError: (e) => toast.error(apiError(e).message) })
  const up = useMutation({ mutationFn: async (f: File) => { const fd = new FormData(); fd.append('image', f); fd.append('source', 'room'); return (await api.post<GalleryImage>('/gallery/', fd)).data },
    onSuccess: (i) => { qc.invalidateQueries({ queryKey: ['gallery'] }); setImgId(i.id); setPicker(false); toast.success('Room photo uploaded') }, onError: (e) => toast.error(apiError(e).message) })
  const fits = c.input.width <= c.roomW && c.input.depth <= c.roomL && c.input.height <= c.roomH
  const pill = (active: boolean) => clsx('rounded-lg border px-3 py-2 text-left text-sm transition-colors', active ? 'border-primary bg-primary/15' : 'border-line bg-card hover:border-primary/40')
  return (
    <div className="grid min-h-full lg:grid-cols-[15rem_1fr]">
      <aside className="space-y-5 border-b border-line p-4 lg:border-b-0 lg:border-r" aria-label="Design options">
        <section><h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Room</h2><div className="grid grid-cols-2 gap-2 lg:grid-cols-1">{ROOMS.map((r) => <button key={r.id} className={pill(c.room === r.id)} aria-pressed={c.room === r.id} onClick={() => set('room', r.id)}>{L(r.label)}</button>)}</div></section>
        <section><h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Furniture</h2><div className="space-y-2">{all.isLoading ? <Skeleton className="h-24" /> : options.map((t) => <button key={t.id} className={pill(c.template === t.slug)} aria-pressed={c.template === t.slug} onClick={() => setC((x) => ({ ...x, template: t.slug, input: t.defaults }))}><span className="block font-medium">{t.name}</span><span className="num text-xs text-muted">{t.defaults.width} x {t.defaults.height} x {t.defaults.depth}</span></button>)}</div></section>
        <section><h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Style</h2><div className="grid grid-cols-2 gap-2 lg:grid-cols-1">{Object.values(STYLES).map((s) => <button key={s.id} className={pill(c.style === s.id)} aria-pressed={c.style === s.id} onClick={() => style(s.id)}><span className="block font-medium">{L(s.label)}</span><span className="text-xs text-muted">{L(s.text)}</span></button>)}</div></section>
      </aside>
      <div className="min-w-0 space-y-5 p-4 sm:p-6">
        <div className="flex flex-wrap items-end gap-3"><div className="min-w-48 flex-1"><h1 className="mb-2 text-2xl font-bold">Interior designer</h1><Input label="Design name" value={name} onChange={(e) => setName(e.target.value)} maxLength={160} /></div>
          <Button icon={<Save size={16} />} loading={save.isPending} onClick={() => save.mutate()}>{designId ? 'Update' : 'Save design'}</Button></div>
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-line px-4 py-2.5"><h2 className="text-sm font-semibold">Room photo</h2><Button size="sm" variant="secondary" icon={<ImagePlus size={14} />} onClick={() => setPicker(true)}>{img ? 'Change' : 'Add photo'}</Button></div>
            {img ? <img src={img.url} alt={img.name} className="max-h-[420px] w-full bg-card2 object-contain" /> : <div className="flex h-64 flex-col items-center justify-center gap-1 px-6 text-center text-sm text-muted"><ImagePlus size={24} />Upload a photo of your room to keep it next to your design.<span className="text-xs">Photos are stored for reference. Automatic room analysis is not available, so enter the room size manually.</span></div>}</Card>
          <div className="space-y-4">{geo.data ? <CabinetViewer boxes={geo.data.boxes} dims={geo.data.dimensions} className="h-[300px]" /> : <Skeleton className="h-[300px]" />}
            <Card className="p-3"><h2 className="mb-1 px-1 text-sm font-semibold">Room plan (top view)</h2><Plan c={c} /></Card></div>
        </div>
        {!fits && <p role="alert" className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning"><AlertTriangle size={16} className="mt-0.5 shrink-0" />The furniture is larger than the room in at least one dimension. Check the sizes.</p>}
      </div>
      <Modal open={picker} onClose={() => setPicker(false)} title="Room photo" wide>
        <FileUploader accept="image/png,image/jpeg,image/webp" onFiles={(f) => up.mutate(f[0])} disabled={up.isPending} label="Upload a new room photo" />
        {!!imgs.data?.results.length && <><h3 className="mb-2 mt-5 text-sm font-semibold">Your room photos</h3><div className="grid grid-cols-3 gap-2 sm:grid-cols-4">{imgs.data.results.map((i) => <button key={i.id} onClick={() => { setImgId(i.id); setPicker(false) }} className="overflow-hidden rounded-lg border border-line hover:border-primary"><img src={i.url} alt={i.name} className="aspect-square w-full object-cover" /></button>)}</div></>}</Modal>
      <RightPanel>
        <PanelSection title="Colors"><div className="space-y-3"><div><p className="mb-1.5 text-xs text-muted">Furniture</p><Swatches value={c.color} onChange={(v) => set('color', v)} /></div><div><p className="mb-1.5 text-xs text-muted">Walls</p><Swatches value={c.wallColor} onChange={(v) => set('wallColor', v)} /></div></div></PanelSection>
        <PanelSection title="Furniture dimensions"><div className="grid grid-cols-2 gap-3">{(['width', 'height', 'depth'] as const).map((k) => <NumberField key={k} label={k[0].toUpperCase() + k.slice(1)} unit="mm" value={c.input[k]} onChange={(n) => set('input', { ...c.input, [k]: n })} />)}<NumberField label="Shelves" value={c.input.shelves} onChange={(n) => set('input', { ...c.input, shelves: n })} /><NumberField label="Doors" value={c.input.doors} onChange={(n) => set('input', { ...c.input, doors: n })} /><NumberField label="Drawers" value={c.input.drawers} onChange={(n) => set('input', { ...c.input, drawers: n })} /></div></PanelSection>
        <PanelSection title="Room dimensions"><div className="grid grid-cols-2 gap-3"><NumberField label="Width" unit="mm" value={c.roomW} onChange={(n) => set('roomW', n)} /><NumberField label="Length" unit="mm" value={c.roomL} onChange={(n) => set('roomL', n)} /><NumberField label="Height" unit="mm" value={c.roomH} onChange={(n) => set('roomH', n)} /></div></PanelSection>
        <PanelSection title="Layout"><div className="space-y-3"><Select label="Place against wall" value={c.wall} onChange={(e) => set('wall', e.target.value as Wall)} options={[{ value: 'north', label: 'North (top)' }, { value: 'south', label: 'South (bottom)' }, { value: 'west', label: 'West (left)' }, { value: 'east', label: 'East (right)' }]} />
          <Select label="Alignment" value={c.align} onChange={(e) => set('align', e.target.value as Align)} options={[{ value: 'start', label: 'Start' }, { value: 'center', label: 'Center' }, { value: 'end', label: 'End' }]} />
          <Textarea label="Notes" value={c.notes} onChange={(e) => set('notes', e.target.value)} maxLength={1000} /></div></PanelSection>
      </RightPanel>
    </div>
  )
}
