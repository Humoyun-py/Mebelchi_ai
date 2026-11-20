import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowUp, Boxes, Check, Copy, FileText, ImagePlus, Mic, MicOff, Paperclip, PencilRuler, Plus, RefreshCw, Scissors, Share2, ThumbsDown, ThumbsUp, Trash2, X, History } from 'lucide-react'
import clsx from 'clsx'
import { api, apiError, downloadBlob } from '../../lib/api'
import type { ChatMessage, Conversation, CuttingList, GalleryImage, Page, UserFile } from '../../lib/types'
import { useAuth } from '../../stores/auth'
import { useT } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { Dropdown } from '../../components/ui/Dropdown'
import { ConfirmDialog, Modal } from '../../components/ui/Modal'
import { Skeleton } from '../../components/ui/Misc'
import { toast } from '../../components/ui/Toast'
import { Tooltip } from '../../components/ui/Tooltip'

interface Attachment { type: 'image' | 'file'; id: number; name: string; preview?: string }

type SR = { new (): { lang: string; interimResults: boolean; onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null; start(): void; stop(): void } }

function MessageView({ m, onEdit, onRegen, onFeedback, onDelete, onAction }: { m: ChatMessage; onEdit: (m: ChatMessage) => void; onRegen: (m: ChatMessage) => void; onFeedback: (m: ChatMessage, f: 'like' | 'dislike') => void; onDelete: (m: ChatMessage) => void; onAction: (m: ChatMessage, a: string) => void }) {
  const [copied, setCopied] = useState(false); const user = m.role === 'user'
  const copy = async () => { try { await navigator.clipboard.writeText(m.content); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { toast.error('Copy failed') } }
  const btn = 'rounded-md p-1.5 text-muted hover:bg-card2 hover:text-fg'
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className={clsx('group flex', user ? 'justify-end' : 'justify-start')}>
      <div className={clsx('max-w-[92%] sm:max-w-[80%]', user && 'items-end')}>
        <div className={clsx('rounded-2xl px-4 py-3', user ? 'bg-primary text-on-primary' : 'border border-line bg-card')}>
          {m.attachments.length > 0 && <div className="mb-2 flex flex-wrap gap-1.5">{m.attachments.map((a) => <span key={`${a.type}${a.id}`} className="flex items-center gap-1.5 rounded-md bg-black/20 px-2 py-1 text-xs">{a.type === 'image' ? <ImagePlus size={12} /> : <FileText size={12} />}{a.name}</span>)}</div>}
          {user ? <p className="whitespace-pre-wrap text-[15px]">{m.content}</p> : <div className="prose-chat"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>}
          {!user && m.metadata.actions && m.metadata.input && <div className="mt-3 flex flex-wrap gap-2">{m.metadata.actions.map((a) => <Button key={a.type} size="sm" variant="secondary" icon={a.type === 'open_3d' ? <Boxes size={14} /> : <Scissors size={14} />} onClick={() => onAction(m, a.type)}>{a.label}</Button>)}</div>}
        </div>
        <div className={clsx('mt-1 flex gap-0.5 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100 sm:group-focus-within:opacity-100', user && 'justify-end')}>
          <Tooltip label={copied ? 'Copied' : 'Copy'} side="top"><button className={btn} onClick={copy} aria-label="Copy message">{copied ? <Check size={15} /> : <Copy size={15} />}</button></Tooltip>
          {user ? <Tooltip label="Edit" side="top"><button className={btn} onClick={() => onEdit(m)} aria-label="Edit message"><PencilRuler size={15} /></button></Tooltip> : (<>
            <Tooltip label="Regenerate" side="top"><button className={btn} onClick={() => onRegen(m)} aria-label="Regenerate response"><RefreshCw size={15} /></button></Tooltip>
            <Tooltip label="Like" side="top"><button className={clsx(btn, m.feedback === 'like' && '!text-success')} onClick={() => onFeedback(m, 'like')} aria-label="Like" aria-pressed={m.feedback === 'like'}><ThumbsUp size={15} /></button></Tooltip>
            <Tooltip label="Dislike" side="top"><button className={clsx(btn, m.feedback === 'dislike' && '!text-danger')} onClick={() => onFeedback(m, 'dislike')} aria-label="Dislike" aria-pressed={m.feedback === 'dislike'}><ThumbsDown size={15} /></button></Tooltip></>)}
          <Tooltip label="Delete" side="top"><button className={btn} onClick={() => onDelete(m)} aria-label="Delete message"><Trash2 size={15} /></button></Tooltip>
        </div>
      </div>
    </motion.div>
  )
}

export default function Chat() {
  const t = useT(); const { id } = useParams(); const nav = useNavigate(); const qc = useQueryClient(); const user = useAuth((s) => s.user)!
  const [text, setText] = useState(''); const [atts, setAtts] = useState<Attachment[]>([]); const [uploading, setUploading] = useState(false); const [editing, setEditing] = useState<ChatMessage | null>(null)
  const [editText, setEditText] = useState(''); const [delMsg, setDelMsg] = useState<ChatMessage | null>(null); const [delConv, setDelConv] = useState<Conversation | null>(null)
  const [listening, setListening] = useState(false); const [voiceNote, setVoiceNote] = useState(false)
  const bottom = useRef<HTMLDivElement>(null); const imgIn = useRef<HTMLInputElement>(null); const pdfIn = useRef<HTMLInputElement>(null); const drawIn = useRef<HTMLInputElement>(null); const ta = useRef<HTMLTextAreaElement>(null)
  const recRef = useRef<InstanceType<SR> | null>(null)
  const convs = useQuery({ queryKey: ['conversations'], queryFn: async () => (await api.get<Page<Conversation>>('/conversations/', { params: { page_size: 50 } })).data })
  const msgs = useQuery({ queryKey: ['messages', id], enabled: !!id, queryFn: async () => (await api.get<ChatMessage[]>(`/conversations/${id}/messages/`)).data })
  const [pending, setPending] = useState<ChatMessage | null>(null)
  const list = useMemo(() => [...(msgs.data ?? []), ...(pending ? [pending] : [])], [msgs.data, pending])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [list.length])
  useEffect(() => { const el = ta.current; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 180) + 'px' } }, [text])
  useEffect(() => () => recRef.current?.stop(), [])

  const send = useMutation({
    mutationFn: async (content: string) => {
      let cid = id
      if (!cid) { cid = String((await api.post<Conversation>('/conversations/', {})).data.id) }
      const res = await api.post<ChatMessage[]>(`/conversations/${cid}/messages/`, { content, attachments: atts.map(({ type, id: aid }) => ({ type, id: aid })) })
      return { cid, res: res.data }
    },
    onMutate: (content) => { setPending({ id: -1, role: 'user', content, attachments: atts.map((a) => ({ type: a.type, id: a.id, name: a.name })), metadata: {}, feedback: '', created_at: '' }); setText(''); setAtts([]) },
    onSuccess: ({ cid }) => { qc.invalidateQueries({ queryKey: ['conversations'] }); qc.invalidateQueries({ queryKey: ['messages', cid] }).then(() => setPending(null)); if (!id) nav(`/app/assistant/${cid}`, { replace: true }) },
    onError: (e) => { setPending(null); toast.error(apiError(e).message) },
  })
  const submit = () => { const c = text.trim(); if (c && !send.isPending) send.mutate(c) }
  const refresh = () => qc.invalidateQueries({ queryKey: ['messages', id] })
  const edit = useMutation({ mutationFn: async () => api.patch(`/messages/${editing!.id}/`, { content: editText }), onSuccess: () => { setEditing(null); refresh() }, onError: (e) => toast.error(apiError(e).message) })
  const regen = useMutation({ mutationFn: (m: ChatMessage) => api.post(`/messages/${m.id}/regenerate/`), onSuccess: refresh, onError: (e) => toast.error(apiError(e).message) })
  const fb = useMutation({ mutationFn: ({ m, f }: { m: ChatMessage; f: string }) => api.post(`/messages/${m.id}/feedback/`, { feedback: f }), onSuccess: refresh })
  const delM = useMutation({ mutationFn: (m: ChatMessage) => api.delete(`/messages/${m.id}/`), onSuccess: () => { setDelMsg(null); refresh() } })
  const delC = useMutation({ mutationFn: (c: Conversation) => api.delete(`/conversations/${c.id}/`), onSuccess: (_r, c) => { setDelConv(null); qc.invalidateQueries({ queryKey: ['conversations'] }); if (String(c.id) === id) nav('/app/assistant') } })

  const action = async (m: ChatMessage, type: string) => {
    const i = m.metadata.input; if (!i) return
    if (type === 'open_3d') nav(`/app/editor?cab=${[i.width, i.height, i.depth, i.thickness, i.shelves, i.doors, i.drawers].join(',')}`)
    else try { const l = (await api.post<CuttingList>('/cutting-lists/from-calculation/', { ...i, name: `Chat ${i.width}x${i.height}x${i.depth}` })).data; toast.success('Cutting list created'); nav(`/app/cutting-lists/${l.id}`) } catch (e) { toast.error(apiError(e).message) }
  }
  const upload = async (files: File[], kind: 'image' | 'pdf' | 'drawing') => {
    setUploading(true)
    try {
      for (const f of files) {
        const fd = new FormData()
        if (kind === 'pdf') { fd.append('file', f); const { data } = await api.post<UserFile>('/files/', fd); setAtts((a) => [...a, { type: 'file', id: data.id, name: data.name }]) }
        else { fd.append('image', f); fd.append('source', kind === 'drawing' ? 'drawing' : 'upload'); const { data } = await api.post<GalleryImage>('/gallery/', fd); setAtts((a) => [...a, { type: 'image', id: data.id, name: data.name, preview: data.url }]) }
      }
    } catch (e) { toast.error(apiError(e).message) } finally { setUploading(false) }
  }
  const startVoice = () => {
    const Rec = ((window as unknown as { SpeechRecognition?: SR; webkitSpeechRecognition?: SR }).SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: SR }).webkitSpeechRecognition)
    if (!Rec) { toast.info('Voice input is not supported in this browser.'); return }
    if (listening) { recRef.current?.stop(); return }
    const r = new Rec(); r.lang = user.language === 'ru' ? 'ru-RU' : user.language === 'uz' ? 'uz-UZ' : 'en-US'; r.interimResults = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setText((x) => (x ? x + ' ' : '') + t) }
    r.onend = () => setListening(false); r.onerror = () => { setListening(false); toast.error('Voice input failed.') }
    recRef.current = r; setListening(true); r.start()
  }
  const share = async () => { try { await downloadBlob(`/conversations/${id}/export/`, 'conversation.md') } catch { toast.error('Export failed') } }

  const history = (
    <ul className="space-y-0.5">{convs.data?.results.map((c) => (
      <li key={c.id} className={clsx('group flex items-center rounded-lg', String(c.id) === id ? 'bg-card2' : 'hover:bg-card2/60')}>
        <button onClick={() => nav(`/app/assistant/${c.id}`)} className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm">{c.title}</button>
        <button onClick={() => setDelConv(c)} aria-label={`Delete conversation ${c.title}`} className="mr-1 rounded p-1 text-muted opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100"><Trash2 size={14} /></button></li>))}
      {convs.data && !convs.data.results.length && <li className="px-3 py-4 text-xs text-muted">No conversations yet.</li>}</ul>
  )
  return (
    <div className="flex h-[calc(100dvh-3.5rem)]">
      <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-line p-3 lg:block" aria-label="Conversation history">
        <Button className="mb-3 w-full" variant="secondary" icon={<Plus size={16} />} onClick={() => nav('/app/assistant')}>{t('chat.new')}</Button>{convs.isLoading ? <Skeleton className="h-40" /> : history}</aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line px-4 py-2 lg:hidden">
          <Dropdown align="left" trigger={<Button size="sm" variant="secondary" icon={<History size={14} />}>{t('chat.history')}</Button>} items={(convs.data?.results ?? []).map((c) => ({ label: c.title.slice(0, 30), onClick: () => nav(`/app/assistant/${c.id}`) }))} />
          <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={() => nav('/app/assistant')}>New</Button></div>
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {!id && !pending ? (
              <div className="pt-[8vh] text-center"><h1 className="text-3xl font-bold">{t('chat.title')}</h1>
                <p className="mx-auto mt-3 max-w-lg text-sm text-muted">{t('chat.sub')}</p>
                <div className="mx-auto mt-8 grid max-w-xl gap-2">{['chat.s1', 'chat.s2', 'chat.s3', 'chat.s4'].map((k) => t(k)).map((s) => <button key={s} onClick={() => { setText(s); ta.current?.focus() }} className="rounded-xl border border-line bg-card px-4 py-3 text-left text-sm transition-colors hover:border-primary/50 hover:bg-card2">{s}</button>)}</div></div>
            ) : msgs.isError ? <div className="pt-[10vh] text-center"><p role="alert" className="text-sm text-danger">{t('chat.notfound')}</p><Button className="mt-4" variant="secondary" onClick={() => nav('/app/assistant')}>{t('chat.new')}</Button></div>
            : msgs.isLoading ? <Skeleton className="h-32" /> : list.map((m) => <MessageView key={m.id} m={m} onEdit={(x) => { setEditing(x); setEditText(x.content) }} onRegen={(x) => regen.mutate(x)} onFeedback={(x, f) => fb.mutate({ m: x, f })} onDelete={setDelMsg} onAction={action} />)}
            {send.isPending && <div className="flex gap-1.5 px-2" aria-label="Assistant is working">{[0, 1, 2].map((i) => <motion.span key={i} className="h-2 w-2 rounded-full bg-muted" animate={{ opacity: [0.3, 1, 0.3] }} transition={{ repeat: Infinity, duration: 1, delay: i * 0.15 }} />)}</div>}
            <div ref={bottom} />
          </div>
        </div>
        <div className="border-t border-line bg-bg px-4 pb-4 pt-3">
          <div className="mx-auto max-w-3xl">
            {atts.length > 0 && <div className="mb-2 flex flex-wrap gap-2">{atts.map((a) => <span key={`${a.type}${a.id}`} className="flex items-center gap-2 rounded-lg border border-line bg-card px-2 py-1.5 text-xs">
              {a.preview ? <img src={a.preview} alt="" className="h-8 w-8 rounded object-cover" /> : <FileText size={16} />}<span className="max-w-32 truncate">{a.name}</span>
              <button aria-label={`Remove ${a.name}`} onClick={() => setAtts(atts.filter((x) => x !== a))} className="text-muted hover:text-fg"><X size={14} /></button></span>)}</div>}
            <div className="rounded-2xl border border-line bg-card p-2 focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/20">
              <textarea ref={ta} value={text} rows={1} maxLength={4000} onChange={(e) => setText(e.target.value)} aria-label="Message" placeholder={t('chat.placeholder')}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }} className="max-h-44 w-full resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted" />
              <div className="flex items-center gap-1">
                <Dropdown align="left" trigger={<button aria-label="Attach file" disabled={uploading} className="rounded-lg p-2 text-muted hover:bg-card2 hover:text-fg disabled:opacity-50"><Paperclip size={18} /></button>} items={[
                  { label: 'Upload image', icon: <ImagePlus size={16} />, onClick: () => imgIn.current?.click() }, { label: 'Upload PDF', icon: <FileText size={16} />, onClick: () => pdfIn.current?.click() }, { label: 'Upload drawing', icon: <PencilRuler size={16} />, onClick: () => drawIn.current?.click() }]} />
                <button onClick={() => (listening || localStorage.getItem('mebelchi.voice-ok') ? startVoice() : setVoiceNote(true))} aria-label={listening ? 'Stop voice input' : 'Voice input'} aria-pressed={listening} className={clsx('rounded-lg p-2 hover:bg-card2', listening ? 'text-danger' : 'text-muted hover:text-fg')}>{listening ? <MicOff size={18} /> : <Mic size={18} />}</button>
                {id && <button onClick={share} aria-label="Share conversation (download Markdown)" className="rounded-lg p-2 text-muted hover:bg-card2 hover:text-fg"><Share2 size={18} /></button>}
                <div className="flex-1" />{uploading && <span className="text-xs text-muted">Uploading...</span>}
                <Button size="sm" onClick={submit} disabled={!text.trim() || send.isPending} aria-label="Send" className="!w-9 !px-0"><ArrowUp size={18} /></Button></div>
            </div>
            <p className="mt-2 text-center text-[11px] text-muted">{t('chat.foot')}</p>
            <input ref={imgIn} type="file" hidden accept="image/png,image/jpeg,image/webp" onChange={(e) => { upload(Array.from(e.target.files ?? []), 'image'); e.target.value = '' }} />
            <input ref={drawIn} type="file" hidden accept="image/png,image/jpeg,image/webp" onChange={(e) => { upload(Array.from(e.target.files ?? []), 'drawing'); e.target.value = '' }} />
            <input ref={pdfIn} type="file" hidden accept="application/pdf" onChange={(e) => { upload(Array.from(e.target.files ?? []), 'pdf'); e.target.value = '' }} />
          </div></div>
      </div>
      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit message" footer={<><Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button><Button loading={edit.isPending} disabled={!editText.trim()} onClick={() => edit.mutate()}>Save and regenerate</Button></>}>
        <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={4} maxLength={4000} aria-label="Message text" className="w-full rounded-lg border border-line bg-card2 p-3 text-sm outline-none focus:border-primary" />
        <p className="mt-2 text-xs text-muted">Messages after this one will be replaced.</p></Modal>
      <Modal open={voiceNote} onClose={() => setVoiceNote(false)} title="Voice input" footer={<><Button variant="ghost" onClick={() => setVoiceNote(false)}>Cancel</Button><Button onClick={() => { try { localStorage.setItem('mebelchi.voice-ok', '1') } catch { /* ignore */ } setVoiceNote(false); startVoice() }}>Continue</Button></>}>
        <p className="text-sm text-muted">Voice input uses your browser's built-in speech recognition. Depending on the browser, audio may be processed by the browser vendor's servers. MEBELCHI AI itself does not send audio to any AI service.</p></Modal>
      <ConfirmDialog open={!!delMsg} onClose={() => setDelMsg(null)} title="Delete message" message="This message will be permanently removed." loading={delM.isPending} onConfirm={() => delMsg && delM.mutate(delMsg)} />
      <ConfirmDialog open={!!delConv} onClose={() => setDelConv(null)} title="Delete conversation" message={`"${delConv?.title}" will be permanently deleted.`} loading={delC.isPending} onConfirm={() => delConv && delC.mutate(delConv)} />
    </div>
  )
}
