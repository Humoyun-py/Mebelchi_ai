import clsx from 'clsx'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import type { CalcResult, PriceLine } from '../lib/types'
import { fmtMoney } from '../lib/format'
import type { PriceForm } from '../lib/workshop'
import { Switch } from './ui/Field'
import { Badge, DataTable, type Column } from './ui/Misc'
import { useT } from '../lib/i18n'

function Money({ label, value, onChange, suffix, id, text, maxLength }: { label: string; value: string; onChange: (v: string) => void; suffix?: string; id: string; text?: boolean; maxLength?: number }) {
  return (
    <div className="flex flex-col justify-end">
      <label htmlFor={id} className="mb-1 block text-xs font-medium leading-tight text-muted">{label}</label>
      <div className="relative">
        <input id={id} inputMode={text ? 'text' : 'decimal'} value={value} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} placeholder="-"
          className={clsx('h-9 w-full rounded-lg border border-line bg-card2 px-3 text-sm text-fg outline-none focus:border-primary focus:ring-4 focus:ring-primary/20', text ? '' : 'num', suffix ? 'pr-14' : '')} />
        {suffix && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-muted">{suffix}</span>}
      </div>
    </div>
  )
}

/** Price estimate: the user types prices, the server does the arithmetic. Anything left empty is reported as missing, never guessed. */
export function PricingPanel({ result, form, onChange, catalog, onCatalog, error }: {
  result: CalcResult | undefined; form: PriceForm; onChange: (f: PriceForm) => void; catalog: boolean; onCatalog: (v: boolean) => void; error?: string
}) {
  const t = useT(); const p = result?.pricing; const cur = p?.currency ?? form.currency
  const set = (patch: Partial<PriceForm>) => onChange({ ...form, ...patch })
  const boards = result ? Object.values(result.summary.by_material) : []
  const lineName = (l: PriceLine) => (l.category === 'hardware' ? (t('hw.' + l.item) === 'hw.' + l.item ? l.item : t('hw.' + l.item)) : l.category === 'edge_banding' ? t('price.edgeLine') : l.category === 'labor' ? t('price.laborLine') : l.item)
  const cols: Column<PriceLine & { id: number }>[] = [
    { key: 'i', header: t('price.item'), render: (l) => <div><p className="font-medium">{lineName(l)}</p><p className="text-xs text-muted">{t('price.cat.' + l.category)}</p></div> },
    { key: 'q', header: t('f.qty'), className: 'num whitespace-nowrap text-right', render: (l) => `${l.quantity} ${l.unit}` },
    { key: 'u', header: t('price.unit'), className: 'num hidden text-right sm:table-cell', render: (l) => (l.unit_price === null ? <Badge tone="warning">{t('price.noPrice')}</Badge> : fmtMoney(l.unit_price)) },
    { key: 'a', header: t('price.amount'), className: 'num text-right', render: (l) => (l.amount === null ? '-' : fmtMoney(l.amount)) },
  ]
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">{t('price.intro')}</p>
      <div className="flex items-center justify-between gap-3 rounded-lg border border-line bg-card2/50 p-3">
        <div><p className="text-sm font-medium">{t('price.catalog')}</p><p className="text-xs text-muted">{t('price.catalogHint')}</p></div>
        <Switch checked={catalog} onChange={onCatalog} label={t('price.catalog')} />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <Money id="pc" text label={t('price.currency')} value={form.currency} maxLength={8} onChange={(v) => set({ currency: v })} />
        <Money id="pw" label={t('price.waste')} value={form.waste} onChange={(v) => set({ waste: v })} suffix="%" />
        <Money id="pm" label={t('price.markup')} value={form.markup} onChange={(v) => set({ markup: v })} suffix="%" />
        <Money id="pe" label={t('price.edge')} value={form.edge} onChange={(v) => set({ edge: v })} suffix="/ m" />
        <Money id="pl" label={t('price.labor')} value={form.labor} onChange={(v) => set({ labor: v })} suffix="/ m2" />
      </div>
      {!!boards.length && (<div><h3 className="mb-2 text-sm font-semibold">{t('price.boards')}</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{boards.map((b) => { const key = `${b.material} ${b.thickness}`
          return <Money key={key} id={`pb-${key}`} label={`${b.material} ${b.thickness} mm`} value={form.board[key] ?? ''} suffix="/ m2" onChange={(v) => set({ board: { ...form.board, [key]: v } })} /> })}</div></div>)}
      {!!result?.hardware?.length && (<div><h3 className="mb-2 text-sm font-semibold">{t('price.hardware')}</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{result.hardware.map((h) => (
          <Money key={h.name} id={`ph-${h.name}`} label={`${t('hw.' + h.name) === 'hw.' + h.name ? h.name : t('hw.' + h.name)} x${h.quantity}`} value={form.hardware[h.name] ?? ''} suffix="/ pc"
            onChange={(v) => set({ hardware: { ...form.hardware, [h.name]: v } })} />))}</div></div>)}
      {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</p>}
      {!p ? <p className="rounded-lg border border-dashed border-line p-4 text-center text-sm text-muted">{t('price.empty')}</p> : (
        <div className="space-y-3" aria-live="polite">
          <div className={clsx('flex items-start gap-2 rounded-lg border p-3 text-sm', p.complete ? 'border-success/30 bg-success/10 text-success' : 'border-warning/30 bg-warning/10 text-warning')} role="status">
            {p.complete ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
            <span>{p.complete ? t('price.complete') : t('price.partial').replace('{n}', String(p.missing.length))}</span></div>
          <DataTable columns={cols} rows={p.lines.map((l, i) => ({ ...l, id: i }))} />
          <dl className="ml-auto max-w-sm space-y-1.5 text-sm">
            {(['board', 'edge_banding', 'hardware', 'labor'] as const).map((k) => <div key={k} className="flex justify-between"><dt className="text-muted">{t('price.cat.' + k)}</dt><dd className="num">{fmtMoney(p.subtotals[k], cur)}</dd></div>)}
            <div className="flex justify-between border-t border-line pt-1.5 font-medium"><dt>{t('price.cost')}</dt><dd className="num">{fmtMoney(p.manufacturing_cost, cur)}</dd></div>
            {p.markup_pct > 0 && <div className="flex justify-between"><dt className="text-muted">{t('price.markupLine').replace('{n}', String(p.markup_pct))}</dt><dd className="num">{fmtMoney(p.markup_amount, cur)}</dd></div>}
            <div className="flex justify-between border-t border-line pt-1.5 text-base font-semibold"><dt>{t('price.total')}</dt><dd className="num text-primary">{fmtMoney(p.total_price, cur)}</dd></div>
          </dl>
          <p className="text-xs text-muted">{t('price.basis')}</p>
        </div>)}
    </div>
  )
}
