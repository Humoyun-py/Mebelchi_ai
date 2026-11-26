import type { ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { BarChart3, ClipboardList, ListChecks, Lock, Settings, Users } from 'lucide-react'
import { apiError } from '../../lib/api'
import { useT } from '../../lib/i18n'
import { useWorkshop } from '../../hooks/workshops'
import { Breadcrumbs, ErrorState, Skeleton } from '../../components/ui/Misc'
import { Tabs } from '../../components/ui/Tabs'
import { RoleBadge, WorkshopBadge } from '../../components/workshop/common'
import { OverviewTab } from '../../components/workshop/OverviewTab'
import { OrdersTab } from '../../components/workshop/OrdersTab'
import { TasksTab } from '../../components/workshop/TasksTab'
import { TeamTab } from '../../components/workshop/TeamTab'
import { SettingsTab } from '../../components/workshop/SettingsTab'

type Tab = 'overview' | 'orders' | 'tasks' | 'team' | 'settings'

export default function WorkshopDetail() {
  const t = useT(); const { id } = useParams(); const [params, setParams] = useSearchParams(); const q = useWorkshop(id!)
  if (q.isLoading) return <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-8"><Skeleton className="h-8 w-64" /><Skeleton className="h-64" /></div>
  if (q.isError || !q.data) return <div className="mx-auto max-w-6xl p-4 sm:p-8"><Breadcrumbs items={[{ label: t('side.workshops'), to: '/app/workshops' }]} /><div className="mt-4"><ErrorState message={q.error ? (apiError(q.error).message === 'Not found.' ? t('ws.notFound') : apiError(q.error).message) : t('ws.notFound')} /></div></div>
  const ws = q.data; const owner = ws.my_role === 'owner'; const writable = ws.status === 'active'
  const tabs: { id: Tab; label: string; icon: ReactNode }[] = [
    ...(owner ? [{ id: 'overview' as const, label: t('ws.tab.overview'), icon: <BarChart3 size={15} /> }] : []),
    { id: 'orders', label: t('ws.tab.orders'), icon: <ClipboardList size={15} /> }, { id: 'tasks', label: t('ws.tab.tasks'), icon: <ListChecks size={15} /> }, { id: 'team', label: t('ws.tab.team'), icon: <Users size={15} /> },
    ...(owner ? [{ id: 'settings' as const, label: t('ws.tab.settings'), icon: <Settings size={15} /> }] : []),
  ]
  const wanted = params.get('tab') as Tab | null
  const tab: Tab = tabs.some((x) => x.id === wanted) ? (wanted as Tab) : tabs[0].id
  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-8">
      <Breadcrumbs items={[{ label: t('side.workshops'), to: '/app/workshops' }, { label: ws.name }]} />
      <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-bold">{ws.name}</h1><WorkshopBadge s={ws.status} />{ws.my_role && <RoleBadge r={ws.my_role} />}</div>
      {!writable && <p role="status" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning"><Lock size={15} />{ws.status === 'suspended' ? t('ws.bannerSuspended') : ws.status === 'pending' ? t('ws.bannerPending') : ws.status === 'rejected' ? `${t('ws.bannerRejected')} ${ws.review_note ?? ''}` : t('ws.bannerInactive')}</p>}
      <Tabs tabs={tabs} value={tab} onChange={(v) => setParams({ tab: v }, { replace: true })} />
      <div>{{
        overview: <OverviewTab ws={ws} />, orders: <OrdersTab ws={ws} owner={owner} writable={writable} />, tasks: <TasksTab ws={ws} owner={owner} writable={writable} />,
        team: <TeamTab ws={ws} owner={owner} writable={writable} />, settings: <SettingsTab ws={ws} writable={writable} />,
      }[tab]}</div>
    </div>
  )
}
