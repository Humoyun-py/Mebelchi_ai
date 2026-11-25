import { Component, Suspense, useEffect, useMemo, type ReactNode } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { ContactShadows, Line, OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { Box } from '../../lib/types'
import { cameraPose, type View } from '../../lib/editor3d'
import { useT } from '../../lib/i18n'

const S = 0.001 // mm -> m
const setCursor = (c: string) => { document.body.style.cursor = c }

class WebGLBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

/** Text drawn to a canvas texture. (drei's <Html> spawns a second React root, which breaks unmounting on React 19.) */
function Label3D({ position, text, unit }: { position: [number, number, number]; text: string; unit: number }) {
  const { tex, ratio } = useMemo(() => {
    const H = 44, c = document.createElement('canvas'), ctx = c.getContext('2d')!
    const font = '600 26px "Geist Variable", Inter, sans-serif'
    ctx.font = font
    const W = Math.ceil(ctx.measureText(text).width) + 26
    c.width = W; c.height = H
    ctx.font = font
    ctx.fillStyle = 'rgba(2,6,23,0.82)'; ctx.strokeStyle = 'rgba(96,165,250,0.7)'; ctx.lineWidth = 2
    ctx.beginPath(); ctx.roundRect(1, 1, W - 2, H - 2, 8); ctx.fill(); ctx.stroke()
    ctx.fillStyle = '#bae6fd'; ctx.textBaseline = 'middle'; ctx.fillText(text, 13, H / 2 + 1)
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
    return { tex: t, ratio: W / H }
  }, [text])
  useEffect(() => () => tex.dispose(), [tex])
  const h = unit * 0.07
  return <sprite position={position} scale={[h * ratio, h, 1]} renderOrder={10}><spriteMaterial map={tex} depthTest={false} transparent /></sprite>
}

function Dim({ a, b, label, offset, unit }: { a: [number, number, number]; b: [number, number, number]; label: string; offset: [number, number, number]; unit: number }) {
  const p1: [number, number, number] = [a[0] + offset[0], a[1] + offset[1], a[2] + offset[2]]
  const p2: [number, number, number] = [b[0] + offset[0], b[1] + offset[1], b[2] + offset[2]]
  const mid: [number, number, number] = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, (p1[2] + p2[2]) / 2]
  return (
    <group>
      <Line points={[p1, p2]} color="#22d3ee" lineWidth={1.5} />
      <Line points={[a, p1]} color="#22d3ee" lineWidth={0.6} transparent opacity={0.5} />
      <Line points={[b, p2]} color="#22d3ee" lineWidth={0.6} transparent opacity={0.5} />
      <Label3D position={mid} text={label} unit={unit} />
    </group>
  )
}

/** Moves the camera to the requested standard view. Axis views use a very narrow field of view (practically orthographic). */
function ViewRig({ view, dims, resetKey }: { view: View; dims: { width: number; height: number; depth: number }; resetKey: number }) {
  const get = useThree((s) => s.get)   // the live scene state, read inside the effect (the camera is a mutable three.js object, not React state)
  const px = useThree((s) => s.size)
  const { width, height, depth } = dims
  useEffect(() => {
    const st = get(); const camera = st.camera as THREE.PerspectiveCamera; const controls = st.controls as { target: THREE.Vector3; update: () => void } | null
    const pose = cameraPose(view, { width, height, depth }, px.width / Math.max(px.height, 1))
    camera.position.set(...pose.position); camera.up.set(...pose.up); camera.fov = pose.fov; camera.near = 0.05; camera.far = 200
    camera.lookAt(0, 0, 0); camera.updateProjectionMatrix()
    if (controls) { controls.target.set(0, 0, 0); controls.update() }
    st.invalidate()
  }, [view, resetKey, width, height, depth, px.width, px.height, get])
  return null
}

function Model({ boxes, dims, showDims, wire, selected, onSelect }: { boxes: Box[]; dims: { width: number; height: number; depth: number }; showDims: boolean; wire: boolean; selected?: string | null; onSelect?: (b: Box) => void }) {
  const { width: W, height: H, depth: D } = dims
  const cx = (W * S) / 2, cz = (D * S) / 2
  const geoms = useMemo(() => boxes.map((b) => new THREE.BoxGeometry(b.sx * S, b.sy * S, b.sz * S)), [boxes])
  const edges = useMemo(() => geoms.map((g) => new THREE.EdgesGeometry(g)), [geoms])
  const w = W * S, h = H * S, d = D * S, u = Math.max(w, h, d)
  useEffect(() => () => setCursor(''), [])   // never leave the pointer cursor behind when the viewer goes away
  return (
    <group position={[-cx, 0, -cz]}>
      {boxes.map((b, i) => (
        <mesh key={`${b.name}-${i}`} geometry={geoms[i]} position={[(b.x + b.sx / 2) * S, (b.y + b.sy / 2) * S, (b.z + b.sz / 2) * S]} castShadow receiveShadow
          onClick={onSelect ? (e) => { e.stopPropagation(); onSelect(b) } : undefined}
          onPointerOver={onSelect ? (e) => { e.stopPropagation(); setCursor('pointer') } : undefined} onPointerOut={onSelect ? () => setCursor('') : undefined}>
          <meshStandardMaterial color={b.color} roughness={b.kind === 'handle' ? 0.3 : 0.75} metalness={b.kind === 'handle' ? 0.8 : 0} wireframe={wire}
            emissive={selected === b.name ? '#22d3ee' : '#000000'} emissiveIntensity={selected === b.name ? 0.45 : 0} />
          {/* edge outlines are decoration: they must never take part in picking (three's default line threshold is 1 unit = 1 m here, which made every click hit the nearest outline) */}
          {!wire && <lineSegments geometry={edges[i]} raycast={() => null}><lineBasicMaterial color={selected === b.name ? '#22d3ee' : '#000'} transparent opacity={selected === b.name ? 1 : 0.28} /></lineSegments>}
        </mesh>
      ))}
      {showDims && (<>
        <Dim unit={u} a={[0, 0, d]} b={[w, 0, d]} label={`${W} mm`} offset={[0, -0.04, 0.1]} />
        <Dim unit={u} a={[w, 0, d]} b={[w, h, d]} label={`${H} mm`} offset={[0.1, 0, 0]} />
        <Dim unit={u} a={[w, 0, 0]} b={[w, 0, d]} label={`${D} mm`} offset={[0.1, -0.04, 0]} />
      </>)}
    </group>
  )
}

export function CabinetViewer({ boxes, dims, showDims = true, wire = false, autoRotate = false, className = 'h-[420px]', interactive = true, view = 'perspective', resetKey = 0, selected, onSelect }: {
  boxes: Box[]; dims: { width: number; height: number; depth: number }; showDims?: boolean; wire?: boolean; autoRotate?: boolean; className?: string; interactive?: boolean
  /** Standard camera view; changing it (or `resetKey`) moves the camera there. */
  view?: View; resetKey?: number
  /** Name of the highlighted component, and the click handler (null = clicked empty space). Pointer picking is on when onSelect is given. */
  selected?: string | null; onSelect?: (b: Box | null) => void
}) {
  const t = useT(); const axis = view !== 'perspective'
  const size = Math.max(dims.width, dims.height, dims.depth) * S
  const dist = size * 1.55 + 0.5
  const fallback = <div className={`flex items-center justify-center rounded-[14px] border border-line bg-card2 p-6 text-center text-sm text-muted ${className}`}>3D preview needs WebGL, which is unavailable in this browser. All calculations still work.</div>
  return (
    <WebGLBoundary fallback={fallback}>
      <div data-view={view} data-selected={selected ?? ''} className={`relative overflow-hidden rounded-[14px] border border-line bg-gradient-to-b from-card2 to-card ${className}`}>
        <Canvas shadows dpr={[1, 2]} camera={{ position: [dist * 0.8, dist * 0.55, dist], fov: 38, near: 0.05, far: 60 }} frameloop={autoRotate ? 'always' : 'demand'}
          aria-label="3D furniture preview" gl={{ antialias: true, preserveDrawingBuffer: false }} onPointerMissed={() => onSelect?.(null)}>
          <hemisphereLight args={['#dbeafe', '#1e293b', 0.9]} />
          <directionalLight position={[4, 6, 5]} intensity={1.8} castShadow shadow-mapSize={[1024, 1024]} />
          <directionalLight position={[-4, 3, -3]} intensity={0.5} />
          <Suspense fallback={null}>
            <group position={[0, -(dims.height * S) / 2, 0]}>
              <Model boxes={boxes} dims={dims} showDims={showDims} wire={wire} selected={selected} onSelect={onSelect ? (b) => onSelect(b) : undefined} />
              <ContactShadows position={[0, -0.002, 0]} opacity={0.5} scale={size * 4} blur={2.4} far={size * 2} />
              <gridHelper args={[size * 6, 24, '#334155', '#1e293b']} position={[0, -0.003, 0]} />
            </group>
          </Suspense>
          <OrbitControls makeDefault enabled={interactive} enablePan enableDamping target={[0, 0, 0]} autoRotate={autoRotate && !axis} autoRotateSpeed={1.1} enableRotate={!axis}
            minDistance={size * 0.8} maxDistance={axis ? size * 400 : size * 8} maxPolarAngle={axis ? Math.PI : Math.PI / 2 + 0.1} />
          <ViewRig view={view} dims={dims} resetKey={resetKey} />
        </Canvas>
        {interactive && <p className="pointer-events-none absolute bottom-2 left-3 text-[11px] text-muted">{axis ? t('ed.hint.axis') : t('ed.hint.orbit')}{onSelect ? ` · ${t('ed.hint.pick')}` : ''}</p>}
      </div>
    </WebGLBoundary>
  )
}
