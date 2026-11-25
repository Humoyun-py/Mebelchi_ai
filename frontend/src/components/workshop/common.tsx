import type { MemberRole, MemberStatus, OrderStatus, PaymentStatus, TaskPriority, TaskStatus, WorkshopStatus } from '../../lib/types'
import { orderTone, payTone, priorityTone, taskTone, workshopTone } from '../../lib/workshop'
import { useT } from '../../lib/i18n'
import { Badge } from '../ui/Misc'

export const OrderBadge = ({ s }: { s: OrderStatus }) => { const t = useT(); return <Badge tone={orderTone[s]}>{t(`order.st.${s}`)}</Badge> }
export const PayBadge = ({ s }: { s: PaymentStatus }) => { const t = useT(); return <Badge tone={payTone[s]}>{t(`pay.${s}`)}</Badge> }
export const TaskBadge = ({ s }: { s: TaskStatus }) => { const t = useT(); return <Badge tone={taskTone[s]}>{t(`task.st.${s}`)}</Badge> }
export const PriorityBadge = ({ p }: { p: TaskPriority }) => { const t = useT(); return <Badge tone={priorityTone[p]}>{t(`task.pr.${p}`)}</Badge> }
export const WorkshopBadge = ({ s }: { s: WorkshopStatus }) => { const t = useT(); return <Badge tone={workshopTone[s]}>{t(`ws.st.${s}`)}</Badge> }
export const RoleBadge = ({ r }: { r: MemberRole }) => { const t = useT(); return <Badge tone={r === 'owner' ? 'primary' : 'neutral'}>{t(`role.${r}`)}</Badge> }
export const MemberStatusBadge = ({ s }: { s: MemberStatus }) => { const t = useT(); return <Badge tone={s === 'active' ? 'success' : s === 'invited' ? 'warning' : 'neutral'}>{t(`mstatus.${s}`)}</Badge> }
