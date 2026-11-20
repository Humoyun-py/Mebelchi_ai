import { useRef, useState, type DragEvent } from 'react'
import { UploadCloud } from 'lucide-react'
import clsx from 'clsx'

export function FileUploader({ accept, multiple, maxMB = 10, onFiles, label = 'Drop files here or click to browse', disabled }: {
  accept: string; multiple?: boolean; maxMB?: number; onFiles: (f: File[]) => void; label?: string; disabled?: boolean
}) {
  const ref = useRef<HTMLInputElement>(null); const [over, setOver] = useState(false); const [err, setErr] = useState('')
  const take = (list: FileList | null) => {
    if (!list) return
    const files = Array.from(list)
    const big = files.find((f) => f.size > maxMB * 1048576)
    if (big) { setErr(`${big.name} is larger than ${maxMB} MB.`); return }
    setErr(''); onFiles(multiple ? files : files.slice(0, 1))
    if (ref.current) ref.current.value = ''
  }
  const drop = (e: DragEvent) => { e.preventDefault(); setOver(false); if (!disabled) take(e.dataTransfer.files) }
  return (
    <div>
      <div role="button" tabIndex={0} aria-disabled={disabled} onClick={() => !disabled && ref.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && !disabled && ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={drop}
        className={clsx('flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[14px] border border-dashed px-4 py-8 text-center transition-colors', over ? 'border-primary bg-primary/5' : 'border-line hover:border-muted/60', disabled && 'pointer-events-none opacity-50')}>
        <UploadCloud size={24} className="text-muted" aria-hidden /><p className="text-sm">{label}</p><p className="text-xs text-muted">Max {maxMB} MB each</p>
      </div>
      <input ref={ref} type="file" hidden accept={accept} multiple={multiple} onChange={(e) => take(e.target.files)} />
      {err && <p role="alert" className="mt-2 text-xs text-danger">{err}</p>}
    </div>
  )
}
