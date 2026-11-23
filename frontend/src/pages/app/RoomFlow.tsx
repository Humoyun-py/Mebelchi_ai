import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, DraftingCompass, RotateCcw } from 'lucide-react'
import { api, apiError } from '../../lib/api'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { ConfirmDialog } from '../../components/ui/Modal'
import { ErrorState, Progress, Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { ChoiceStep, NumberGroupStep, OpeningsStep, PhotoStep } from '../../components/room/steps'
import { Furnish } from '../../components/room/Furnish'
import { useActiveFlows, useFlow, useFlowActions, useItemActions, useStartFlow } from '../../hooks/roomFlow'
import { fill, type FlowView, type Opening, type RoomItem } from '../../lib/roomFlow'
import { useL, useT } from '../../lib/i18n'

const OUT_OF_DATE = new Set(['step_mismatch', 'not_furnishing', 'not_generated'])

function Summary({ flow, onNew }: { flow: FlowView; onNew: () => void }) {
  const t = useT()
  return (
    <Card className="space-y-4 p-6">
      <h2 className="text-lg font-semibold">{t('rf.saved')}</h2>
      <p className="text-sm text-muted">{t('rf.savedText')}</p>
      <p className="text-xs text-muted">{t('rf.items')}: {flow.items?.length ?? 0}</p>
      <p className="text-xs text-muted">{t('rf.disclaimer')}</p>
      <div className="flex flex-wrap gap-2"><Link to="/app/designs"><Button>{t('rf.openDesigns')}</Button></Link><Button variant="secondary" icon={<RotateCcw size={16} />} onClick={onNew}>{t('rf.newDesign')}</Button></div>
    </Card>
  )
}

function FlowScreen({ id, onRestart }: { id: number; onRestart: () => void }) {
  const t = useT(), L = useL(), qc = useQueryClient()
  const q = useFlow(id)
  const { answer, back, abandon } = useFlowActions(id)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [confirm, setConfirm] = useState(false)
  const reload = () => qc.invalidateQueries({ queryKey: ['room-flow', id] })
  const items = useItemActions(id, () => qc.getQueryData<FlowView>(['room-flow', id])?.rev ?? null, () => toast.info(t('rf.conflict')))

  const submit = (step: string, value: unknown) => answer.mutate({ step, value }, {
    onSuccess: () => setErrors({}),
    onError: (e) => {
      const err = apiError(e), code = err.fields.code
      if (code && OUT_OF_DATE.has(code)) { reload(); return }
      if (code === 'not_active') { toast.error(t('rf.closed')); reload(); return }
      setErrors(err.fields); toast.error(err.message)
    },
  })
  const photo = useMutation({
    mutationFn: async (file: File) => { const fd = new FormData(); fd.append('image', file); fd.append('source', 'room'); return (await api.post<{ id: number }>('/gallery/', fd)).data.id },
    onSuccess: (imageId) => submit('photo', { image_id: imageId }), onError: (e) => toast.error(apiError(e).message),
  })

  if (q.isError) return <ErrorState message={t('rf.loadErr')} onRetry={q.refetch} />
  const flow = q.data
  if (!flow) return <Skeleton className="h-96" />
  const d = flow.descriptor
  const open = flow.status === 'active'
  const busy = answer.isPending || photo.isPending || back.isPending
  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="num text-sm text-muted" data-testid="progress">{fill(t('rf.step'), { i: d.index, n: d.total })}</p>
          {open && <Button size="sm" variant="ghost" icon={<RotateCcw size={14} />} onClick={() => setConfirm(true)}>{t('rf.startOver')}</Button>}
        </div>
        <Progress tone="success" value={(100 * d.index) / d.total} label={fill(t('rf.step'), { i: d.index, n: d.total })} />
        {d.kind !== 'summary' && <><h2 className="mt-4 text-xl font-semibold">{L(d.title)}</h2>
          <p className="mt-1 text-sm text-muted">{L(d.prompt)}</p></>}
      </div>

      {!open && d.kind !== 'summary' ? (
        <Card className="space-y-3 p-6"><p>{t('rf.closed')}</p><Button onClick={onRestart}>{t('rf.newDesign')}</Button></Card>
      ) : d.kind === 'choice' ? <ChoiceStep d={d} busy={busy} onPick={(v) => submit(d.step, v)} />
        : d.kind === 'photo' ? <PhotoStep busy={busy} onUpload={(f) => photo.mutate(f)} onSkip={() => submit('photo', { skip: true })} />
        : d.kind === 'number_group' ? <NumberGroupStep key={d.step} d={d} busy={busy} errors={errors} onSubmit={(v) => submit(d.step, v)} />
        : d.kind === 'openings' ? <OpeningsStep key={d.step} d={d} busy={busy} errors={errors} onSubmit={(v: Opening[]) => submit('openings', v)} />
        : d.kind === 'furnish' ? <Furnish flow={flow} busy={items.busy} finishing={answer.isPending} onAdd={(slug) => items.add.mutate({ template: slug })}
            onPatch={(itemId, patch: Partial<RoomItem>) => items.update.mutate({ id: itemId, patch })} onRemove={(itemId) => items.remove.mutate(itemId)} onFinish={() => submit('furnish', { done: true })} />
        : <Summary flow={flow} onNew={onRestart} />}

      {open && d.can_back && d.kind !== 'furnish' && <Button variant="ghost" icon={<ArrowLeft size={16} />} loading={back.isPending} onClick={() => { setErrors({}); back.mutate() }}>{t('rf.back')}</Button>}
      {open && d.kind === 'furnish' && <Button variant="ghost" icon={<ArrowLeft size={16} />} loading={back.isPending} onClick={() => back.mutate()}>{t('rf.back')}</Button>}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} title={t('rf.startOverTitle')} message={t('rf.startOverMsg')} confirmLabel={t('rf.startOverConfirm')} loading={abandon.isPending}
        onConfirm={() => abandon.mutate(undefined, { onSuccess: () => { setConfirm(false); onRestart() } })} />
    </div>
  )
}

export default function RoomFlowPage() {
  const t = useT()
  const [params, setParams] = useSearchParams()
  const fromUrl = Number(params.get('flow')) || null
  const active = useActiveFlows()
  const start = useStartFlow()
  const id = fromUrl ?? active.data?.results[0]?.id ?? null
  const go = (flowId: number) => setParams({ flow: String(flowId) }, { replace: true })
  const begin = () => start.mutate(undefined, { onSuccess: (v) => go(v.id) })
  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold"><DraftingCompass size={24} className="text-primary" aria-hidden />{t('rf.title')}</h1>
      <div className="mt-6">
        {!fromUrl && active.isLoading ? <Skeleton className="h-64" />
          : id == null ? (
            <Card className="max-w-xl space-y-4 p-6"><p className="text-sm text-muted">{t('rf.intro')}</p><Button loading={start.isPending} onClick={begin}>{t('rf.start')}</Button></Card>
          ) : <FlowScreen key={id} id={id} onRestart={begin} />}
      </div>
    </div>
  )
}
