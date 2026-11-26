import { useEffect, useRef } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, apiError } from '../../lib/api'
import { Button } from '../../components/ui/Button'
import { ErrorState, Skeleton } from '../../components/ui/Misc'
import { useImportDesign, useStartRoom } from '../../hooks/rooms'
import { useT } from '../../lib/i18n'

const GOALS = ['kitchen', 'bedroom', 'living', 'wardrobe', 'office', 'other']

function Waiting({ text }: { text: string }) {
  return <div className="mx-auto max-w-xl space-y-3 p-6" role="status" aria-live="polite"><p className="text-sm text-muted">{text}</p><Skeleton className="h-10 w-64" /><Skeleton className="h-40" /></div>
}

/** /app/rooms/new?goal=kitchen: starts a room design (and answers the first question when the goal is known), then replaces itself with the real URL,
 *  so reloading never creates a second design. */
export function RoomStart() {
  const t = useT(); const nav = useNavigate(); const [params] = useSearchParams(); const start = useStartRoom(); const ran = useRef(false)
  const goal = params.get('goal'); const known = goal && GOALS.includes(goal) ? goal : null
  useEffect(() => {
    if (ran.current) return; ran.current = true
    start.mutateAsync().then(async (f) => {
      if (known) { try { await api.post(`/rooms/${f.id}/answer/`, { step: 'goal', value: known }) } catch { /* the wizard still opens on the goal question */ } }
      nav(`/app/rooms/${f.id}`, { replace: true })
    }).catch(() => { /* shown below */ })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  if (start.isError) return <div className="mx-auto max-w-xl p-6"><ErrorState message={apiError(start.error).message || t('room.startErr')} /><Link to="/app/rooms" className="mt-3 inline-block text-sm text-primary hover:underline">{t('room.toList')}</Link></div>
  return <Waiting text={t('room.starting')} />
}

/** /app/rooms/import/:designId: opens an old interior design in the room designer. The server copies it; the old design stays as it was. */
export function RoomImport() {
  const t = useT(); const nav = useNavigate(); const { designId } = useParams(); const imp = useImportDesign(); const ran = useRef(false)
  const id = Number(designId)
  useEffect(() => {
    if (ran.current || !Number.isInteger(id) || id <= 0) return; ran.current = true
    imp.mutateAsync(id).then((f) => nav(`/app/rooms/${f.id}`, { replace: true })).catch(() => { /* shown below */ })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])
  if (!Number.isInteger(id) || id <= 0) return <Navigate to="/app/designs" replace />
  if (imp.isError) {
    const e = apiError(imp.error); const detail = Object.entries(e.fields).map(([k, v]) => `${k}: ${v}`).join('; ')
    return <div className="mx-auto max-w-xl space-y-3 p-6"><ErrorState message={`${t('room.importErr')} ${detail || e.message}`} />
      <p className="text-sm text-muted">{t('room.importHint')}</p><Link to="/app/designs"><Button variant="secondary">{t('room.toDesigns2')}</Button></Link></div>
  }
  return <Waiting text={t('room.importing')} />
}

/** The old /app/interior address (bookmarks, old links, old Home buttons) keeps working and lands in the room designer. */
export function LegacyInterior() {
  const [params] = useSearchParams(); const design = params.get('design'); const room = params.get('room')
  if (design && /^\d+$/.test(design)) return <Navigate to={`/app/rooms/import/${design}`} replace />
  if (room && GOALS.includes(room)) return <Navigate to={`/app/rooms/new?goal=${room}`} replace />
  return <Navigate to="/app/rooms" replace />
}
