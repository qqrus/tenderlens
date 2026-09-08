import { BookOpenCheck, Quote, X } from 'lucide-react'
import { useRef, useSyncExternalStore } from 'react'
import type { CitationResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'
import { PdfViewer } from './PdfViewer'
import { useDialogFocus } from './useDialogFocus'

const mobileQuery = '(max-width: 760px)'
const subscribeMobile = (callback: () => void) => {
  const media = window.matchMedia(mobileQuery)
  media.addEventListener('change', callback)
  return () => media.removeEventListener('change', callback)
}

type Props = {
  open?: boolean
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
  open = false,
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
  const panelRef = useRef<HTMLElement>(null)
  const mobile = useSyncExternalStore(subscribeMobile, () => window.matchMedia(mobileQuery).matches)
  const modal = mobile && open
  useDialogFocus(panelRef, modal, onClose)
  return (
    <aside
      className="source-panel"
      ref={panelRef}
      tabIndex={-1}
      role={modal ? 'dialog' : undefined}
      aria-modal={modal || undefined}
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
            {pick('цитата из документа', 'quote from the document')}
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
        highlightQuote={citation?.page_number === pageNumber ? citation.quote : null}
      />
    </aside>
  )
}
