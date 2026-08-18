import { BookOpenCheck, Quote, X } from 'lucide-react'
import type { CitationResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'
import { PdfViewer } from './PdfViewer'

type Props = {
  citation: CitationResponse | null
  sourceUrl: string | null
  pageNumber: number
  onPageChange: (page: number) => void
  onClose: () => void
  sourceLoading?: boolean
  sourceError?: string | null
  onSourceRetry?: () => void
}

export function CitationDrawer({
  citation,
  sourceUrl,
  pageNumber,
  onPageChange,
  onClose,
  sourceLoading,
  sourceError,
  onSourceRetry,
}: Props) {
  const { pick } = useLocale()
  return (
    <aside
      className="source-panel"
      data-open={Boolean(citation)}
      aria-label={pick('Панель источника', 'Source panel')}
    >
      <header className="source-header">
        <div>
          <span className="source-icon">
            <BookOpenCheck aria-hidden="true" />
          </span>
          <div>
            <span className="eyebrow">{pick('Проверяемый источник', 'Verifiable source')}</span>
            <h2>
              {pick('Документ · стр.', 'Document · p.')} {pageNumber}
            </h2>
          </div>
        </div>
        <button
          className="icon-button source-close"
          type="button"
          onClick={onClose}
          aria-label={pick('Закрыть источник', 'Close source')}
        >
          <X aria-hidden="true" />
        </button>
      </header>

      {citation && (
        <blockquote className="citation-quote">
          <Quote aria-hidden="true" />
          <p>{citation.quote}</p>
          <footer>
            {pick('Страница', 'Page')} {citation.page_number} ·{' '}
            {pick('точная цитата backend', 'exact backend quote')}
          </footer>
        </blockquote>
      )}

      <PdfViewer
        sourceUrl={sourceUrl}
        pageNumber={pageNumber}
        onPageChange={onPageChange}
        sourceLoading={sourceLoading}
        sourceError={sourceError}
        onSourceRetry={onSourceRetry}
      />
    </aside>
  )
}
