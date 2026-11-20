import { Check, Globe } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../stores/auth'
import { useUI } from '../stores/ui'
import { Dropdown } from './ui/Dropdown'

const LANGS = [['uz', "O'zbekcha", 'UZ'], ['ru', 'Русский', 'RU'], ['en', 'English', 'EN']] as const

/** Header language switcher. Saved to the profile when logged in. */
export function LanguageMenu() {
  const { language, setLanguage } = useUI(); const user = useAuth((s) => s.user)
  const pick = async (l: 'en' | 'uz' | 'ru') => {
    setLanguage(l)
    if (user) { try { await api.patch('/users/me/', { language: l }) } catch { /* local choice still applied */ } }
  }
  return (
    <Dropdown trigger={<button aria-label="Change language" className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm text-muted hover:bg-card2 hover:text-fg"><Globe size={17} /><span className="font-medium">{language.toUpperCase()}</span></button>}
      items={LANGS.map(([code, name]) => ({ label: name, icon: language === code ? <Check size={15} className="text-primary" /> : <span className="w-[15px]" />, onClick: () => pick(code) }))} />
  )
}
