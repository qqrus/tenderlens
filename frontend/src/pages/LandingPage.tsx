import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  Banknote,
  CalendarClock,
  FileCheck2,
  FileText,
  Gavel,
  LayoutGrid,
  ListFilter,
  Plus,
  Search,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { humanizeError, listDocuments, uploadDocument } from '../api/client'
import type { DocumentResponse, DocumentStatusValue } from '../api/types'
import { ErrorState } from '../components/ErrorState'
import { LanguageToggle } from '../components/LanguageToggle'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { UploadDropzone } from '../components/UploadDropzone'
import { useFileSession } from '../context/FileSessionContext'
import { useLocale } from '../i18n/LocaleContext'

type StatusFilter = 'all' | DocumentStatusValue

export function LandingPage() {
  const { locale, pick } = useLocale()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const fileSession = useFileSession()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [uploadOpen, setUploadOpen] = useState(searchParams.get('upload') === '1')
  const statusLabels: Record<DocumentStatusValue, string> = {
    uploaded: pick('Загружен', 'Uploaded'),
    processing: pick('Анализируется', 'Processing'),
    ready: pick('Анализ завершён', 'Analysis complete'),
    failed: pick('Ошибка обработки', 'Processing failed'),
  }

  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: () => listDocuments(100, 0),
    refetchInterval: (query) =>
      query.state.data?.items.some((document) =>
        ['uploaded', 'processing'].includes(document.status),
      )
        ? 2000
        : false,
  })

  const upload = useMutation({
    mutationFn: uploadDocument,
    onSuccess: async ({ document }) => {
      if (selectedFile) fileSession.setFile(selectedFile)
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
      navigate(`/documents/${document.id}`)
    },
  })

  const filteredDocuments = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase('ru')
    return (documentsQuery.data?.items ?? []).filter((document) => {
      const matchesSearch =
        !normalizedSearch ||
        document.original_filename.toLocaleLowerCase('ru').includes(normalizedSearch)
      const matchesStatus = statusFilter === 'all' || document.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [documentsQuery.data?.items, search, statusFilter])

  const closeUpload = () => {
    if (upload.isPending) return
    setUploadOpen(false)
    setSelectedFile(null)
    if (searchParams.has('upload')) {
      searchParams.delete('upload')
      setSearchParams(searchParams, { replace: true })
    }
  }

  return (
    <main className="library-shell">
      <aside className="library-sidebar">
        <Link className="product-brand" to="/" aria-label="TenderLens — документы">
          <span className="product-wordmark">
            Tender<span>Lens</span>
          </span>
          <span className="brand-brackets" aria-hidden="true" />
        </Link>

        <nav className="library-nav" aria-label={pick('Навигация', 'Navigation')}>
          <Link data-active="true" to="/">
            <FileText aria-hidden="true" />
            <span>{pick('Документы', 'Documents')}</span>
            <span className="nav-count">{documentsQuery.data?.total ?? '—'}</span>
          </Link>
          <button type="button" onClick={() => setUploadOpen(true)}>
            <Plus aria-hidden="true" />
            <span>{pick('Новый анализ', 'New analysis')}</span>
          </button>
        </nav>

        <div className="sidebar-system-note">
          <span>
            <ShieldCheck aria-hidden="true" /> {pick('Источники в PDF', 'Sources in PDF')}
          </span>
          <p>
            {pick(
              'Каждый вывод можно открыть на исходной странице документа.',
              'Every finding opens on its source PDF page.',
            )}
          </p>
          <LanguageToggle />
        </div>
      </aside>

      <section className="library-main">
        <header className="library-header">
          <div>
            <span className="page-kicker">{pick('Рабочее пространство', 'Workspace')}</span>
            <h1>{pick('Тендеры под контролем', 'Tenders under control')}</h1>
            <p>
              {pick(
                'Документы, ключевые условия и подтверждённые источники — в одном контуре.',
                'Documents, key conditions and verified sources in one workspace.',
              )}
            </p>
          </div>
          <button
            className="primary-button upload-launch"
            type="button"
            onClick={() => setUploadOpen(true)}
          >
            <Upload aria-hidden="true" /> {pick('Загрузить PDF', 'Upload PDF')}
          </button>
        </header>

        <EvidenceAtlas />

        <section className="history-section" aria-labelledby="history-heading">
          <div className="history-heading">
            <div>
              <span className="page-kicker">{pick('Архив', 'Archive')}</span>
              <h2 id="history-heading">{pick('История анализа', 'Analysis history')}</h2>
            </div>
            <div className="history-controls">
              <label className="search-control">
                <Search aria-hidden="true" />
                <span className="sr-only">{pick('Найти документ', 'Find document')}</span>
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={pick('Найти документ', 'Find document')}
                />
              </label>
              <label className="filter-control">
                <ListFilter aria-hidden="true" />
                <span className="sr-only">{pick('Фильтр статуса', 'Status filter')}</span>
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                >
                  <option value="all">{pick('Все статусы', 'All statuses')}</option>
                  <option value="ready">{pick('Готовые', 'Ready')}</option>
                  <option value="processing">{pick('В работе', 'Processing')}</option>
                  <option value="uploaded">{pick('Загруженные', 'Uploaded')}</option>
                  <option value="failed">{pick('С ошибкой', 'Failed')}</option>
                </select>
              </label>
            </div>
          </div>

          {documentsQuery.isLoading ? (
            <LoadingSkeleton />
          ) : documentsQuery.isError ? (
            <ErrorState
              message={humanizeError(documentsQuery.error, locale)}
              onRetry={() => void documentsQuery.refetch()}
            />
          ) : filteredDocuments.length ? (
            <DocumentTable
              documents={filteredDocuments}
              statusLabels={statusLabels}
              locale={locale}
              pick={pick}
            />
          ) : (
            <div className="history-empty">
              <span className="history-empty-icon">
                <FileCheck2 aria-hidden="true" />
              </span>
              <div>
                <h3>
                  {documentsQuery.data?.total
                    ? pick('Документы не найдены', 'No documents found')
                    : pick(
                        'Здесь появится история анализа',
                        'Your analysis history will appear here',
                      )}
                </h3>
                <p>
                  {documentsQuery.data?.total
                    ? pick(
                        'Измените запрос или фильтр статуса.',
                        'Change the search or status filter.',
                      )
                    : pick(
                        'Загрузите первый тендерный PDF — он сохранится в этой библиотеке.',
                        'Upload your first tender PDF — it will stay in this library.',
                      )}
                </p>
              </div>
              {!documentsQuery.data?.total && (
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setUploadOpen(true)}
                >
                  {pick('Загрузить документ', 'Upload document')}
                </button>
              )}
            </div>
          )}
        </section>
      </section>

      {uploadOpen && (
        <div
          className="upload-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeUpload()
          }}
        >
          <section
            className="upload-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
          >
            <header>
              <div>
                <span className="page-kicker">{pick('Новый анализ', 'New analysis')}</span>
                <h2 id="upload-title">{pick('Загрузите тендерный PDF', 'Upload a tender PDF')}</h2>
                <p>
                  {pick(
                    'После обработки документ останется в общей истории.',
                    'The document will remain in the shared history after processing.',
                  )}
                </p>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={closeUpload}
                aria-label={pick('Закрыть загрузку', 'Close upload')}
              >
                <X aria-hidden="true" />
              </button>
            </header>
            <UploadDropzone
              selectedFile={selectedFile}
              isUploading={upload.isPending}
              onFileChange={setSelectedFile}
              onUpload={() => selectedFile && upload.mutate(selectedFile)}
            />
            {upload.isError && (
              <p className="upload-api-error" role="alert">
                {humanizeError(upload.error, locale)}
              </p>
            )}
          </section>
        </div>
      )}
    </main>
  )
}

function EvidenceAtlas() {
  const { pick } = useLocale()
  const nodes = [
    {
      id: 'deadline',
      label: pick('Сроки', 'Deadlines'),
      note: pick('даты и этапы', 'dates and stages'),
      icon: CalendarClock,
    },
    {
      id: 'budget',
      label: pick('Бюджет', 'Budget'),
      note: pick('суммы и валюта', 'amounts and currency'),
      icon: Banknote,
    },
    {
      id: 'penalty',
      label: pick('Штрафы', 'Penalties'),
      note: pick('санкции и пени', 'fines and damages'),
      icon: Gavel,
    },
    {
      id: 'requirement',
      label: pick('Требования', 'Requirements'),
      note: pick('допуски и опыт', 'eligibility and experience'),
      icon: FileCheck2,
    },
  ] as const

  return (
    <section className="atlas-panel" aria-labelledby="atlas-title">
      <div className="atlas-caption">
        <span className="page-kicker">
          {pick('Документ · атлас доказательств', 'Document · evidence atlas')}
        </span>
        <h2 id="atlas-title">
          {pick('От условия — к странице первоисточника', 'From condition to source page')}
        </h2>
      </div>
      <div className="atlas-stage">
        <div className="atlas-grid" aria-hidden="true" />
        {nodes.map(({ id, label, note, icon: Icon }) => (
          <div className={`atlas-node atlas-node-${id}`} key={id}>
            <span>
              <Icon aria-hidden="true" />
            </span>
            <div>
              <strong>{label}</strong>
              <small>{note}</small>
            </div>
          </div>
        ))}
        <div className="atlas-line atlas-line-a" aria-hidden="true" />
        <div className="atlas-line atlas-line-b" aria-hidden="true" />
        <div className="atlas-line atlas-line-c" aria-hidden="true" />
        <div className="atlas-line atlas-line-d" aria-hidden="true" />
        <div className="atlas-document" aria-hidden="true">
          <span className="document-fold" />
          <span className="document-label">{pick('Тендерный PDF', 'Tender PDF')}</span>
          <span className="document-line document-line-1" />
          <span className="document-line document-line-2" />
          <span className="document-line document-line-3" />
          <span className="document-table" />
          <span className="document-line document-line-4" />
          <span className="document-line document-line-5" />
        </div>
        <div className="atlas-footnote">
          <LayoutGrid aria-hidden="true" />{' '}
          {pick(
            '4 категории · точные цитаты · страницы PDF',
            '4 categories · exact quotes · PDF pages',
          )}
        </div>
      </div>
    </section>
  )
}

function DocumentTable({
  documents,
  statusLabels,
  locale,
  pick,
}: {
  documents: DocumentResponse[]
  statusLabels: Record<DocumentStatusValue, string>
  locale: 'ru' | 'en'
  pick: (ru: string, en: string) => string
}) {
  return (
    <div className="document-table-wrap">
      <div className="document-table-head" aria-hidden="true">
        <span>{pick('Документ', 'Document')}</span>
        <span>{pick('Статус', 'Status')}</span>
        <span>{pick('Дата', 'Date')}</span>
        <span>{pick('Страниц', 'Pages')}</span>
        <span>{pick('Размер', 'Size')}</span>
        <span />
      </div>
      <div className="document-rows">
        {documents.map((document) => (
          <Link className="document-row" to={`/documents/${document.id}`} key={document.id}>
            <span className="document-cell document-name-cell">
              <span className="pdf-file-icon">
                <FileText aria-hidden="true" />
              </span>
              <span>
                <strong>{document.original_filename}</strong>
                <small>{shortId(document.id)}</small>
              </span>
            </span>
            <span className="document-cell status-cell" data-status={document.status}>
              <i /> {statusLabels[document.status]}
            </span>
            <span className="document-cell mono-cell">
              {formatDate(document.created_at, locale)}
            </span>
            <span className="document-cell mono-cell">{document.page_count ?? '—'}</span>
            <span className="document-cell mono-cell">{formatBytes(document.size_bytes)}</span>
            <span className="document-cell row-action">
              {pick('Открыть', 'Open')} <ArrowRight aria-hidden="true" />
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}

function shortId(id: string) {
  return `ID ${id.slice(0, 8).toUpperCase()}`
}

function formatDate(value: string, locale: 'ru' | 'en') {
  return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}
