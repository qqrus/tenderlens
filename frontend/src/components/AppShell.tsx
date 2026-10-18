import { ArrowLeft, BarChart3, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useLocale } from '../i18n/LocaleContext'
import { LanguageToggle } from './LanguageToggle'

export type WorkspaceTab = 'summary' | 'conditions' | 'risks' | 'questions'
type Props = { activeTab: WorkspaceTab; onTabChange: (tab: WorkspaceTab) => void; filename: string }

export function AppShell({ activeTab, onTabChange }: Props) {
  const { pick } = useLocale()
  const items: Array<{ id: WorkspaceTab; label: string }> = [
    { id: 'summary', label: pick('Обзор', 'Overview') },
    { id: 'conditions', label: pick('Условия', 'Conditions') },
    { id: 'risks', label: pick('Риски', 'Risks') },
    { id: 'questions', label: pick('Вопросы', 'Questions') },
  ]
  return (
    <>
      <header className="graphite-topbar">
        <Link
          className="product-brand"
          to="/"
          aria-label={pick('TenderLens — документы', 'TenderLens — documents')}
        >
          <span className="product-wordmark">
            Tender<span>Lens</span>
          </span>
        </Link>
        <nav aria-label={pick('Навигация', 'Navigation')}>
          <Link to="/">
            <ArrowLeft aria-hidden="true" />
            {pick('Документы', 'Documents')}
          </Link>
          <Link to="/ml-report">
            <BarChart3 aria-hidden="true" />
            {pick('ML-эксперименты', 'ML experiments')}
          </Link>
          <Link to="/?upload=1">
            <Plus aria-hidden="true" />
            {pick('Новый PDF', 'New PDF')}
          </Link>
        </nav>
        <LanguageToggle />
      </header>
      <nav className="workspace-tabs" aria-label={pick('Разделы документа', 'Document sections')}>
        {items.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            aria-current={activeTab === id ? 'page' : undefined}
            data-active={activeTab === id}
            onClick={() => onTabChange(id)}
          >
            {label}
          </button>
        ))}
      </nav>
    </>
  )
}
