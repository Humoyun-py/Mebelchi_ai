import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './stores/auth'
import { Toaster } from './components/ui/Toast'
import { Skeleton } from './components/ui/Misc'
import AppShell from './layouts/AppShell'
import Landing from './pages/landing/Landing'
import Legal from './pages/landing/Legal'
import { ForgotPassword, Login, Register, ResetPassword } from './pages/auth/Auth'
import RoleSelect from './pages/auth/RoleSelect'

const Home = lazy(() => import('./pages/app/Home'))
const Chat = lazy(() => import('./pages/app/Chat'))
const Projects = lazy(() => import('./pages/app/Projects'))
const ProjectDetail = lazy(() => import('./pages/app/ProjectDetail'))
const Calculator = lazy(() => import('./pages/app/Calculator'))
const CuttingLists = lazy(() => import('./pages/app/CuttingLists'))
const Editor = lazy(() => import('./pages/app/Editor'))
const Interior = lazy(() => import('./pages/app/Interior'))
const RoomFlow = lazy(() => import('./pages/app/RoomFlow'))
const Gallery = lazy(() => import('./pages/app/Gallery'))
const Files = lazy(() => import('./pages/app/Files'))
const Designs = lazy(() => import('./pages/app/Designs'))
const SettingsPage = lazy(() => import('./pages/app/Settings'))
const Admin = lazy(() => import('./pages/admin/Admin'))

function Protected({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { user, ready } = useAuth(); const loc = useLocation()
  if (!ready) return <div className="p-8"><Skeleton className="h-8 w-48" /></div>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />
  if (!user.role_selected && loc.pathname !== '/choose-role') return <Navigate to="/choose-role" replace />
  if (admin && !user.is_admin) return <Navigate to="/app" replace />
  return <>{children}</>
}
function Guest({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  if (ready && user) return <Navigate to={user.role_selected ? '/app' : '/choose-role'} replace />
  return <>{children}</>
}
const Fallback = () => <div className="space-y-4 p-6"><Skeleton className="h-8 w-56" /><Skeleton className="h-40 w-full" /><Skeleton className="h-40 w-full" /></div>
const L = ({ children }: { children: ReactNode }) => <Suspense fallback={<Fallback />}>{children}</Suspense>

export default function App() {
  const load = useAuth((s) => s.load)
  useEffect(() => { load() }, [load])
  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/privacy" element={<Legal />} />
        <Route path="/terms" element={<Legal />} />
        <Route path="/login" element={<Guest><Login /></Guest>} />
        <Route path="/register" element={<Guest><Register /></Guest>} />
        <Route path="/forgot-password" element={<Guest><ForgotPassword /></Guest>} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/choose-role" element={<Protected><RoleSelect /></Protected>} />
        <Route path="/app" element={<Protected><AppShell /></Protected>}>
          <Route index element={<L><Home /></L>} />
          <Route path="assistant" element={<L><Chat /></L>} />
          <Route path="assistant/:id" element={<L><Chat /></L>} />
          <Route path="projects" element={<L><Projects /></L>} />
          <Route path="projects/:id" element={<L><ProjectDetail /></L>} />
          <Route path="calculator" element={<L><Calculator /></L>} />
          <Route path="cutting-lists" element={<L><CuttingLists /></L>} />
          <Route path="cutting-lists/:id" element={<L><CuttingLists /></L>} />
          <Route path="editor" element={<L><Editor /></L>} />
          <Route path="interior" element={<L><Interior /></L>} />
          <Route path="room-flow" element={<L><RoomFlow /></L>} />
          <Route path="gallery" element={<L><Gallery /></L>} />
          <Route path="files" element={<L><Files /></L>} />
          <Route path="designs" element={<L><Designs /></L>} />
          <Route path="settings" element={<L><SettingsPage /></L>} />
          <Route path="admin" element={<Protected admin><L><Admin /></L></Protected>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </>
  )
}
