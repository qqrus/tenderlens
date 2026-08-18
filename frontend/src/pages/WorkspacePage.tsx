import { useQuery } from '@tanstack/react-query'
import { FileCheck2 } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { analyzeDocument, downloadDocumentFile, getDocument, humanizeError } from '../api/client'
import type { CitationResponse, DocumentAnalysisResponse, DocumentResponse } from '../api/types'
import { AppShell } from '../components/AppShell'
import type { WorkspaceTab } from '../components/AppShell'
import { ConditionCard } from '../components/ConditionCard'
import { DocumentStatus } from '../components/DocumentStatus'
import { DocumentSummary } from '../components/DocumentSummary'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { LoadingSkeleton } from '../components/LoadingSkeleton'
import { QuestionPanel } from '../components/QuestionPanel'
import { RiskChecklist } from '../components/RiskChecklist'
import { useFileSession } from '../context/FileSessionContext'
import { useLocale } from '../i18n/LocaleContext'

const CitationDrawer = lazy(() =>
  import('../components/CitationDrawer').then((module) => ({ default: module.CitationDrawer })),
)

export function WorkspacePage() {
  const { locale, pick } = useLocale()
  const { documentId = '' } = useParams()
  const { objectUrl } = useFileSession()
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('summary')
  const [selectedCitation, setSelectedCitation] = useState<CitationResponse | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [sourceOpen, setSourceOpen] = useState(false)

  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'ready' || status === 'failed' ? false : 1500
    },
  })

  const analysisQuery = useQuery({
    queryKey: ['analysis', documentId],
    queryFn: () => analyzeDocument(documentId),
    enabled: documentQuery.data?.status === 'ready',
    retry: 1,
  })

  const fileQuery = useQuery({
    queryKey: ['document-file', documentId],
    queryFn: () => downloadDocumentFile(documentId),
    enabled: Boolean(documentId) && documentQuery.data?.status === 'ready' && !objectUrl,
    retry: 1,
    staleTime: Number.POSITIVE_INFINITY,
  })
  const remoteObjectUrl = useBlobObjectUrl(fileQuery.data)
  const pdfSourceUrl = objectUrl ?? remoteObjectUrl

  const fallbackCitation = analysisQuery.data?.conditions[0]?.citation ?? null
  const visibleCitation = selectedCitation ?? fallbackCitation
  const visiblePage = selectedCitation ? pageNumber : (fallbackCitation?.page_number ?? pageNumber)

  const openCitation = (citation: CitationResponse) => {
    setSelectedCitation(citation)
    setPageNumber(citation.page_number)
    setSourceOpen(true)
  }

  if (documentQuery.isLoading) {
    return (
      <main className="standalone-state">
        <LoadingSkeleton />
      </main>
    )
  }

  if (documentQuery.isError || !documentQuery.data) {
    return (
      <main className="standalone-state">
        <ErrorState
          message={humanizeError(documentQuery.error, locale)}
          onRetry={() => void documentQuery.refetch()}
        />
      </main>
    )
  }

  const document = documentQuery.data

  return (
    <main className="workspace-shell" data-source-open={sourceOpen}>
      <AppShell
        activeTab={activeTab}
        onTabChange={setActiveTab}
        filename={document.original_filename}
      />

      <section className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-document-meta">
            <span className="workspace-status-dot" data-status={document.status} />
            <div>
              <strong>{document.original_filename}</strong>
              <span>
                {document.status === 'ready'
                  ? pick('Анализ завершён', 'Analysis complete')
                  : pick('Документ обрабатывается', 'Document is processing')}
                {document.page_count ? ` · ${document.page_count} ${pick('стр.', 'pages')}` : ''}
              </span>
            </div>
          </div>
          <div className="workspace-topbar-actions">
            <span className="workspace-updated">
              {pick('Обновлён', 'Updated')} {formatWorkspaceDate(document.updated_at, locale)}
            </span>
            {visibleCitation && (
              <button className="source-toggle" type="button" onClick={() => setSourceOpen(true)}>
                <FileCheck2 aria-hidden="true" /> {pick('Источник · стр.', 'Source · p.')}{' '}
                {visiblePage}
              </button>
            )}
          </div>
        </header>

        <div className="workspace-scroll">
          {document.status === 'failed' ? (
            <ErrorState
              title={pick('Документ не обработан', 'Document was not processed')}
              message={
                document.error_code === 'no_extractable_text'
                  ? pick(
                      'В PDF не найден извлекаемый текст. Сейчас TenderLens поддерживает текстовые PDF без OCR.',
                      'No extractable text was found. TenderLens currently supports text PDFs without OCR.',
                    )
                  : (document.error_message ??
                    pick(
                      'Backend не смог обработать PDF.',
                      'The backend could not process the PDF.',
                    ))
              }
            />
          ) : document.status !== 'ready' ? (
            <DocumentStatus status={document.status} />
          ) : analysisQuery.isLoading ? (
            <LoadingSkeleton />
          ) : analysisQuery.isError || !analysisQuery.data ? (
            <ErrorState
              title={pick('Анализ временно недоступен', 'Analysis is temporarily unavailable')}
              message={humanizeError(analysisQuery.error, locale)}
              onRetry={() => void analysisQuery.refetch()}
            />
          ) : (
            <WorkspaceContent
              tab={activeTab}
              document={document}
              analysis={analysisQuery.data}
              documentId={documentId}
              onCitationOpen={openCitation}
            />
          )}
        </div>
      </section>

      <Suspense
        fallback={
          <aside
            className="source-panel"
            aria-label={pick('Загружаем источник', 'Loading source')}
          />
        }
      >
        <CitationDrawer
          citation={visibleCitation}
          sourceUrl={pdfSourceUrl}
          pageNumber={visiblePage}
          onPageChange={(page) => {
            setPageNumber(page)
            if (!selectedCitation) setSelectedCitation(visibleCitation)
          }}
          onClose={() => setSourceOpen(false)}
          sourceLoading={!objectUrl && fileQuery.isLoading}
          sourceError={
            !objectUrl && fileQuery.isError ? humanizeError(fileQuery.error, locale) : null
          }
          onSourceRetry={() => void fileQuery.refetch()}
        />
      </Suspense>
      {sourceOpen && (
        <button
          className="drawer-backdrop"
          type="button"
          aria-label={pick('Закрыть источник', 'Close source')}
          onClick={() => setSourceOpen(false)}
        />
      )}
    </main>
  )
}

function useBlobObjectUrl(blob: Blob | undefined) {
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob])

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [url])

  return url
}

type WorkspaceContentProps = {
  tab: WorkspaceTab
  document: DocumentResponse
  analysis: DocumentAnalysisResponse
  documentId: string
  onCitationOpen: (citation: CitationResponse) => void
}

function WorkspaceContent({
  tab,
  document,
  analysis,
  documentId,
  onCitationOpen,
}: WorkspaceContentProps) {
  const { pick } = useLocale()
  if (tab === 'summary') {
    return (
      <DocumentSummary document={document} analysis={analysis} onCitationOpen={onCitationOpen} />
    )
  }

  if (tab === 'conditions') {
    return (
      <section>
        <div className="page-heading">
          <span className="page-kicker">{pick('Извлечённые данные', 'Extracted data')}</span>
          <h1>{pick('Условия документа', 'Document conditions')}</h1>
          <p>
            {pick(
              'Каждое найденное условие связано с точной цитатой и страницей PDF. Технический процент показывает совпадение правила, а не юридическую оценку.',
              'Every extracted condition is linked to an exact quote and PDF page. The technical percentage is a rule match score, not a legal assessment.',
            )}
          </p>
        </div>
        {analysis.conditions.length ? (
          <div className="condition-grid wide">
            {analysis.conditions.map((condition) => (
              <ConditionCard
                key={`${condition.category}-${condition.citation.chunk_id}`}
                condition={condition}
                onCitationOpen={onCitationOpen}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            message={pick(
              'Условия не найдены автоматически. Требуется ручная проверка PDF.',
              'No conditions were found automatically. Manual PDF review is required.',
            )}
          />
        )}
      </section>
    )
  }

  if (tab === 'risks') {
    return (
      <section>
        <div className="page-heading">
          <span className="page-kicker">
            {pick('Консервативная проверка', 'Conservative review')}
          </span>
          <h1>{pick('Сигналы риска', 'Risk signals')}</h1>
          <p>
            {pick(
              'Подтверждённые пункты отделены от категорий, которые система предлагает проверить вручную.',
              'Grounded findings are separated from categories that still require manual review.',
            )}
          </p>
        </div>
        <RiskChecklist risks={analysis.risks} onCitationOpen={onCitationOpen} />
      </section>
    )
  }

  return <QuestionPanel documentId={documentId} onCitationOpen={onCitationOpen} />
}

function formatWorkspaceDate(value: string, locale: 'ru' | 'en') {
  return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-GB', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
