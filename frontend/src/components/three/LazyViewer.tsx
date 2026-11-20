import { lazy, Suspense, type ComponentProps } from 'react'

const Impl = lazy(() => import('./CabinetViewer').then((m) => ({ default: m.CabinetViewer })))

/** three.js is ~1 MB; load it only when a 3D view is actually rendered. */
export function CabinetViewer(props: ComponentProps<typeof Impl>) {
  return (
    <Suspense fallback={<div className={`animate-pulse rounded-[14px] border border-line bg-card2 ${props.className ?? 'h-[420px]'}`} aria-label="Loading 3D view" />}>
      <Impl {...props} />
    </Suspense>
  )
}
