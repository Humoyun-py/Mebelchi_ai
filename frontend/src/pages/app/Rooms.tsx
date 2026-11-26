import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Plus, Sofa, Trash2 } from 'lucide-react'
import { apiError } from '../../lib/api'
import { fmtAgo } from '../../lib/format'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Badge, EmptyState, ErrorState, Skeleton } from '../../components/ui/Misc'
import { ConfirmDialog } from '../../components/ui/Modal'
import { toast } from '../../components/ui/Toast'
import { Wizard } from '../../components/room/Wizard'
import { Workspace } from '../../components/room/Workspace'
import { useAnswer, useBack, useDeleteRoom, useRoomFlow, useRoomList, useStartRoom } from '../../hooks/rooms'
import { useT } from '../../lib/i18n'

function RoomList() {
  const t = useT(); const nav = useNavigate(); const list = useRoomList(); const start = useStartRoom(); const del = useDeleteRoom(); const [ask, setAsk] = useState<number | null>(null)
  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-semibold">{t('room.title')}</h1><p className="mt-1 max-w-xl text-sm text-muted">{t('room.sub')}</p></div>
        <Button icon={<Plus size={16} />} loading={start.isPending} onClick={() => start.mutate(undefined, { onSuccess: (f) => nav(`/app/rooms/${f.id}`), onError: (e) => toast.error(apiError(e).message || t('room.startErr')) })}>{t('room.new')}</Button>
      </div>
      <div className="mt-6 space-y-3">
        {list.isError ? <ErrorState message={t('room.loadErr')} onRetry={() => list.refetch()} />
          : list.isLoading ? <Skeleton className="h-24" />
          : list.data?.results.length ? list.data.results.map((r) => (
            <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="font-medium">{r.goal ? t(`room.goal.${r.goal}`) : t('room.noGoal')}</p>
                <p className="mt-0.5 text-xs text-muted">{fmtAgo(r.updated_at)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={r.status === 'completed' ? 'success' : 'primary'}>{t(`room.status.${r.status}`)}</Badge>
                <Link to={`/app/rooms/${r.id}`}><Button size="sm" variant="secondary">{r.status === 'active' ? t('room.continue') : t('room.open')}</Button></Link>
                <Button size="sm" variant="ghost" aria-label={`${t('common.delete')} #${r.id}`} icon={<Trash2 size={15} />} onClick={() => setAsk(r.id)} />
              </div>
            </Card>))
          : <EmptyState icon={<Sofa size={22} />} title={t('room.empty')} text={t('room.emptyText')} />}
      </div>
      <ConfirmDialog open={ask !== null} onClose={() => setAsk(null)} title={t('room.deleteTitle')} message={t('room.deleteMsg')} confirmLabel={t('common.delete')} cancelLabel={t('common.cancel')} loading={del.isPending}
        onConfirm={() => del.mutate(ask!, { onSuccess: () => setAsk(null), onError: (e) => { setAsk(null); toast.error(apiError(e).message) } })} />
    </div>
  )
}

function RoomDetail({ id }: { id: string }) {
  const t = useT(); const flow = useRoomFlow(id); const answer = useAnswer(id); const back = useBack(id)
  if (flow.isError) { const nf = (flow.error as { response?: { status?: number } })?.response?.status === 404; return <div className="mx-auto max-w-xl p-6"><ErrorState message={nf ? t('room.notFound') : t('room.loadErr')} onRetry={nf ? undefined : () => flow.refetch()} /><Link to="/app/rooms" className="mt-3 inline-block text-sm text-primary hover:underline">{t('room.toList')}</Link></div> }
  if (!flow.data) return <div className="mx-auto max-w-2xl space-y-3 p-6"><Skeleton className="h-10 w-64" /><Skeleton className="h-72" /></div>
  const f = flow.data; const furnish = f.step === 'furnish' || f.step === 'done'
  const err = answer.error ? apiError(answer.error) : back.error ? apiError(back.error) : null
  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><Link to="/app/rooms" aria-label={t('room.toList')} className="rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg"><ArrowLeft size={18} /></Link><h1 className="text-2xl font-semibold">{t('room.title')}</h1></div>
        {f.status === 'completed' && <Link to="/app/designs"><Button variant="secondary" size="sm">{t('room.toDesigns')}</Button></Link>}
      </div>
      {f.status === 'completed' && <p role="status" className="mb-4 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">{t('room.doneBanner')}</p>}
      {furnish && f.room ? (
        <>
          {f.status === 'active' && f.question.index > 0 && <div className="mb-3"><Button variant="ghost" size="sm" onClick={() => back.mutate()} disabled={back.isPending}>{t('room.back')}</Button></div>}
          <Workspace flow={f} readOnly={f.status !== 'active'} />
        </>
      ) : <Wizard flow={f} busy={answer.isPending || back.isPending} error={err} onBack={() => { answer.reset(); back.mutate() }}
          submit={async (step, value) => { back.reset(); try { await answer.mutateAsync({ step, value }) } catch { /* the error is shown inside the wizard */ } }} />}
    </div>
  )
}

export default function Rooms() {
  const { id } = useParams()
  return id ? <RoomDetail key={id} id={id} /> : <RoomList />
}
