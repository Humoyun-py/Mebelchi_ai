import { Link, useLocation } from 'react-router-dom'
import { Logo } from '../../components/Logo'

const DOCS = {
  '/privacy': {
    title: 'Privacy Policy',
    sections: [
      ['What we store', 'Your account details (name, email, phone), your projects, calculations, cutting lists, designs, and the images and files you upload. We also record anonymous-by-feature usage events (for example "calculation" or "export_pdf") and server errors to operate the service.'],
      ['Who can see it', 'Only your account can access your projects and files. Files are served through short-lived signed links. Platform administrators can see account-level data needed to operate the service, such as email, plan and storage totals.'],
      ['AI services', 'MEBELCHI AI does not send your data to any external AI service. Calculations and layouts run on our own servers. Optional voice input uses your browser\'s own speech recognition, which may be processed by your browser vendor.'],
      ['Your choices', 'You can edit your profile, delete individual items, or revoke sessions in Settings. To delete your account and data, contact the operator of this installation.'],
    ],
  },
  '/terms': {
    title: 'Terms of Service',
    sections: [
      ['Professional review required', 'All calculations, cutting lists and layouts are provided for professional review. They are not verified manufacturing instructions. You are responsible for checking dimensions, materials, hardware, grain direction and machine limits before cutting or building.'],
      ['Acceptable use', 'Do not upload unlawful content or attempt to access other users\' data. Automated abuse is rate limited and may be blocked.'],
      ['Plans and payments', 'Paid plans are activated by an administrator after a payment is confirmed. Limits for each plan are shown in Settings.'],
      ['No warranty', 'The service is provided as is. The operator is not liable for material losses resulting from the use of calculated output.'],
    ],
  },
} as const

export default function Legal() {
  const doc = DOCS[useLocation().pathname as keyof typeof DOCS] ?? DOCS['/terms']
  return (
    <div className="min-h-dvh">
      <header className="border-b border-line"><div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4"><Logo /><Link to="/" className="text-sm text-muted hover:text-fg">Back to website</Link></div></header>
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="text-3xl font-bold">{doc.title}</h1>
        <p className="mt-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm text-warning">This is a plain-language template. The operator of this installation must have it reviewed by legal counsel and adapted to local law before launch.</p>
        {doc.sections.map(([h, t]) => <section key={h} className="mt-8"><h2 className="text-lg font-semibold">{h}</h2><p className="mt-2 leading-relaxed text-muted">{t}</p></section>)}
      </main>
    </div>
  )
}
