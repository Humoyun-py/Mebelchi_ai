export const fmtBytes = (n: number) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1073741824).toFixed(2)} GB`
export const fmtDate = (s: string) => new Date(s).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
export const fmtAgo = (s: string) => {
  const d = (Date.now() - new Date(s).getTime()) / 1000
  if (d < 60) return 'just now'
  if (d < 3600) return `${Math.floor(d / 60)} min ago`
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`
  if (d < 604800) return `${Math.floor(d / 86400)} d ago`
  return fmtDate(s)
}
export const num = (v: unknown, d = 0) => { const n = Number(v); return Number.isFinite(n) ? n : d }

/** Money arrives from the API as decimal strings. The platform does not know the workshop's currency, so amounts are shown as plain grouped numbers. */
export const fmtMoney = (v: string | number | null | undefined, currency = '') => {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return `${n.toLocaleString(undefined, { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ''}`
}
export const fmtDateTime = (s: string) => new Date(s).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
/** `<input type="datetime-local">` value <-> ISO string (the input works in local time, the API in UTC). */
export const toLocalInput = (iso: string | null) => { if (!iso) return ''; const d = new Date(iso); const p = (n: number) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}` }
export const fromLocalInput = (v: string) => (v ? new Date(v).toISOString() : null)
