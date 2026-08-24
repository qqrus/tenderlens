import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  FileCheck2,
  LayoutDashboard,
  MessageSquareText,
  Plus,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useLocale } from '../i18n/LocaleContext'
import { LanguageToggle } from './LanguageToggle'

export type WorkspaceTab = 'summary' | 'conditions' | 'risks' | 'questions'

type Props = {
  activeTab: WorkspaceTab
  onTabChange: (tab: WorkspaceTab) => void
  filename: string
}

export function AppShell({ activeTab, onTabChange, filename }: Props) {
  const { pick } = useLocale()
  const items: Array<{ id: WorkspaceTab; label: string; icon: typeof LayoutDashboard }> = [
    { id: 'summary', label: pick('Карта решения', 'Decision map'), icon: LayoutDashboard },
    { id: 'conditions', label: pick('Условия', 'Conditions'), icon: FileCheck2 },
    { id: 'risks', label: pick('Риски', 'Risks'), icon: AlertTriangle },
    { id: 'questions', label: pick('Вопросы', 'Questions'), icon: MessageSquareText },
  ]
  return (
    <aside className="app-sidebar">
      <Link className="product-brand" to="/" aria-label="TenderLens — документы">
        <span className="product-wordmark">
          Tender<span>Lens</span>
        </span>
        <span className="brand-brackets" aria-hidden="true" />
      </Link>

      <Link className="all-documents-link" to="/">
        <ArrowLeft aria-hidden="true" /> {pick('Все документы', 'All documents')}
      </Link>

      <div className="sidebar-document" title={filename}>
        <span>{pick('Текущий документ', 'Current document')}</span>
        <strong>{filename}</strong>
      </div>

      <nav className="sidebar-items" aria-label={pick('Разделы документа', 'Document sections')}>
        {items.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            data-active={activeTab === id}
            onClick={() => onTabChange(id)}
          >
            <Icon aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <Link className="new-document-link" to="/?upload=1">
        <Plus aria-hidden="true" /> {pick('Новый PDF', 'New PDF')}
      </Link>
      <Link className="ml-report-link" to="/ml-report">
        <BarChart3 aria-hidden="true" /> {pick('ML-метрики', 'ML metrics')}
      </Link>
      <LanguageToggle />
    </aside>
  )
}
