import { BarChart3, CheckCircle2, ClipboardList, Clock, Users, Wallet } from 'lucide-react'
import { apiError } from '../../lib/api'
import { fmtMoney } from '../../lib/format'
import { useT } from '../../lib/i18n'
import type { Workshop } from '../../lib/types'
import { useWorkshopStats } from '../../hooks/workshops'
import { Card } from '../ui/Card'
import { ErrorState, Progress, Skeleton, Stat } from '../ui/Misc'

/** Owner-only: every number comes from the statistics endpoint (database aggregates), none is computed or invented here. */
export function OverviewTab({ ws }: { ws: Workshop }) {
  const t = useT(); const q = useWorkshopStats(ws.id)
  if (q.isLoading) return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>
  if (q.isError || !q.data) return <ErrorState message={q.error ? apiError(q.error).message : t('ws.loadErr')} onRetry={() => q.refetch()} />
  const d = q.data; const o = d.orders; const tk = d.tasks
  const done = tk.total - tk.cancelled > 0 ? (100 * tk.completed) / (tk.total - tk.cancelled) : 0
  const money = d.money
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('stat.orders')} value={o.total} hint={`${o.new} ${t('order.st.new').toLowerCase()}`} />
        <Stat label={t('order.st.in_production')} value={o.in_production} />
        <Stat label={t('stat.completed')} value={o.delivered} hint={`${o.cancelled} ${t('order.st.cancelled').toLowerCase()}`} />
        <Stat label={t('stat.employees')} value={d.employees.total} hint={`${d.employees.active} ${t('mstatus.active').toLowerCase()}`} /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5"><h3 className="mb-4 flex items-center gap-2 font-semibold"><ClipboardList size={17} className="text-primary" />{t('stat.ordersByStatus')}</h3>
          <ul className="space-y-2">{(['new', 'confirmed', 'in_production', 'ready', 'delivered', 'cancelled'] as const).map((k) => (
            <li key={k} className="flex items-center gap-3 text-sm"><span className="w-32 shrink-0 text-muted">{t(`order.st.${k}`)}</span>
              <div className="h-2 flex-1 rounded-full bg-card2"><div className="h-full rounded-full bg-primary" style={{ width: `${o.total ? (100 * o[k]) / o.total : 0}%` }} /></div><span className="num w-8 text-right">{o[k]}</span></li>))}</ul></Card>
        <Card className="p-5"><h3 className="mb-4 flex items-center gap-2 font-semibold"><CheckCircle2 size={17} className="text-primary" />{t('stat.tasks')}</h3>
          <div className="mb-3 grid grid-cols-3 gap-3 text-center">{[[t('task.st.pending'), tk.pending], [t('task.st.in_progress'), tk.in_progress + tk.review], [t('task.st.completed'), tk.completed]].map(([k, v]) => (
            <div key={k}><p className="num text-xl font-semibold">{v}</p><p className="text-xs text-muted">{k}</p></div>))}</div>
          <Progress value={done} tone="success" label={t('stat.taskProgress')} />
          <p className="mt-2 flex items-center gap-1.5 text-xs text-muted"><Clock size={13} />{t('stat.overdue')}: <span className={tk.overdue ? 'num font-semibold text-danger' : 'num'}>{tk.overdue}</span></p></Card>
      </div>
      <Card className="p-5"><h3 className="mb-4 flex items-center gap-2 font-semibold"><Wallet size={17} className="text-primary" />{t('stat.money')}</h3>
        <div className="grid gap-4 sm:grid-cols-3">{[[t('stat.value'), money.total_order_value], [t('stat.paid'), money.paid_amount], [t('stat.outstanding'), money.outstanding_amount]].map(([k, v]) => (
          <div key={k}><p className="text-xs text-muted">{k}</p><p className="num text-2xl font-semibold">{fmtMoney(v)}</p></div>))}</div>
        <p className="mt-3 text-xs text-muted">{t('stat.moneyNote')}</p></Card>
      <p className="flex items-center gap-1.5 text-xs text-muted"><BarChart3 size={13} /><Users size={13} />{t('stat.source')}</p>
    </div>
  )
}
