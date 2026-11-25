/** Camera poses for the 3D editor. Pure maths, so it is testable without WebGL.
 *  The scene is centred on the origin (the viewer shifts the cabinet by half its height), distances are in metres. */
export type View = 'perspective' | 'front' | 'side' | 'top'
export const VIEWS: View[] = ['perspective', 'front', 'side', 'top']
const S = 0.001
const AXIS_FOV = 6   // axis views use a very narrow field of view: practically orthographic, so sizes read true

export interface Pose { position: [number, number, number]; up: [number, number, number]; fov: number }

export function cameraPose(view: View, dims: { width: number; height: number; depth: number }, aspect: number): Pose {
  const W = dims.width * S, H = dims.height * S, D = dims.depth * S
  const size = Math.max(W, H, D)
  if (view === 'perspective') { const d = size * 1.55 + 0.5; return { position: [d * 0.8, d * 0.55, d], up: [0, 1, 0], fov: 38 } }
  const [ex, ey, depthAlong] = view === 'front' ? [W, H, D] : view === 'side' ? [D, H, W] : [W, D, H]
  const half = Math.max(ey / 2, ex / 2 / Math.max(aspect, 0.2)) * 1.25            // fit both extents with a margin
  const dist = half / Math.tan((AXIS_FOV * Math.PI) / 360) + depthAlong / 2
  if (view === 'front') return { position: [0, 0, dist], up: [0, 1, 0], fov: AXIS_FOV }
  if (view === 'side') return { position: [dist, 0, 0], up: [0, 1, 0], fov: AXIS_FOV }
  return { position: [0, dist, 0], up: [0, 0, -1], fov: AXIS_FOV }
}
