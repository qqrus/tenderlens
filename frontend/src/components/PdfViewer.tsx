import { ChevronLeft, ChevronRight, FileWarning, LoaderCircle, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLocale } from '../i18n/LocaleContext'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { renderHighlightedPdfText } from './pdfHighlight'
import type { TableAnswerResponse } from '../api/types'
import { tableColors, tableRegions } from './tableHighlight'

pdfjs.GlobalWorkerOptions.workerSrc = `${new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()}?v=5.4.296`

type Props = {
  sourceUrl: string | null
  pageNumber: number
  onPageChange: (page: number) => void
  sourceLoading?: boolean
  sourceError?: string | null
  onSourceRetry?: () => void
  highlightQuote?: string | null
  tableEvidence?: TableAnswerResponse | null
}

export function PdfViewer({
  sourceUrl,
  pageNumber,
  onPageChange,
  sourceLoading,
  sourceError,
  onSourceRetry,
  highlightQuote = null,
  tableEvidence = null,
}: Props) {
  const { pick } = useLocale()
  const frameRef = useRef<HTMLDivElement>(null)
  const [pageCount, setPageCount] = useState(0)
  const [width, setWidth] = useState(520)
  const [geometry, setGeometry] = useState<{
    source: string
    page: number
    width: number
    height: number
  } | null>(null)
  const regions =
    tableEvidence && geometry?.source === sourceUrl && geometry.page === pageNumber
      ? tableRegions(tableEvidence, pageNumber, geometry.width, geometry.height)
      : []

  useEffect(() => {
    const node = frameRef.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.max(160, Math.min(900, entry.contentRect.width - 32)))
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [sourceUrl])

  useEffect(() => {
    if (pageCount && pageNumber > pageCount) onPageChange(pageCount)
  }, [onPageChange, pageCount, pageNumber])

  if (!sourceUrl) {
    return (
      <div className="pdf-unavailable">
        {sourceLoading ? (
          <LoaderCircle className="spin" aria-hidden="true" />
        ) : (
          <FileWarning aria-hidden="true" />
        )}
        <h3>
          {sourceLoading
            ? pick('Загружаем оригинал PDF', 'Loading source PDF')
            : pick('Оригинал PDF недоступен', 'Source PDF unavailable')}
        </h3>
        <p>
          {sourceError ??
            pick(
              'Цитата и номер страницы сохранены рядом. Попробуйте загрузить файл ещё раз.',
              'The quote and page number remain available. Try loading the file again.',
            )}
        </p>
        {sourceError && onSourceRetry && (
          <button className="secondary-button" type="button" onClick={onSourceRetry}>
            <RotateCcw aria-hidden="true" /> {pick('Повторить загрузку PDF', 'Retry PDF download')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="pdf-viewer" ref={frameRef}>
      <div className="pdf-toolbar">
        <button
          className="icon-button"
          type="button"
          onClick={() => onPageChange(Math.max(1, pageNumber - 1))}
          disabled={pageNumber <= 1}
          aria-label={pick('Предыдущая страница', 'Previous page')}
        >
          <ChevronLeft aria-hidden="true" />
        </button>
        <span>
          <strong>{pageNumber}</strong>
          {pageCount ? ` / ${pageCount}` : ''}
        </span>
        <button
          className="icon-button"
          type="button"
          onClick={() => onPageChange(Math.min(pageCount || pageNumber + 1, pageNumber + 1))}
          disabled={Boolean(pageCount && pageNumber >= pageCount)}
          aria-label={pick('Следующая страница', 'Next page')}
        >
          <ChevronRight aria-hidden="true" />
        </button>
      </div>
      <div className="pdf-canvas">
        <Document
          file={sourceUrl}
          onLoadSuccess={({ numPages }) => setPageCount(numPages)}
          loading={
            <div className="pdf-loading">
              <LoaderCircle className="spin" /> {pick('Загружаем PDF', 'Loading PDF')}
            </div>
          }
          error={
            <div className="pdf-loading">
              <FileWarning /> {pick('Не удалось открыть PDF.', 'Could not open PDF.')}
            </div>
          }
        >
          <Page
            key={`${sourceUrl}:${pageNumber}`}
            pageNumber={pageNumber}
            width={width}
            renderTextLayer
            renderAnnotationLayer
            onLoadSuccess={(page) => {
              const viewport = page.getViewport({ scale: 1 })
              // Do not guess transformations for rotated/cropped pages in this prototype.
              const supported = page.rotate === 0 && page.view[0] === 0 && page.view[1] === 0
              setGeometry({
                source: sourceUrl,
                page: pageNumber,
                width: supported ? viewport.width : 0,
                height: supported ? viewport.height : 0,
              })
            }}
            customTextRenderer={({ str }) => renderHighlightedPdfText(str, highlightQuote)}
            onRenderTextLayerSuccess={() => {
              const canvas = frameRef.current?.querySelector('.pdf-canvas')
              const target = canvas?.querySelector('.pdf-citation-highlight')
              if (!canvas || !target) return
              // Scroll only the PDF viewport, never the page or the panel header.
              canvas.scrollBy({
                top:
                  target.getBoundingClientRect().top -
                  canvas.getBoundingClientRect().top -
                  canvas.clientHeight / 2,
                behavior: 'instant',
              })
            }}
          >
            {regions.length === 3 && (
              <div
                className="pdf-geometry-layer"
                aria-label={pick('Области табличной цитаты', 'Table citation regions')}
              >
                {regions.map(({ role, ...style }) => (
                  <div
                    key={role}
                    data-table-role={role}
                    className="pdf-geometry-box"
                    style={{
                      ...style,
                      borderColor: tableColors[role],
                      backgroundColor: `${tableColors[role]}22`,
                    }}
                  />
                ))}
              </div>
            )}
          </Page>
          {tableEvidence?.evidence.page_number === pageNumber &&
            geometry?.page === pageNumber &&
            regions.length !== 3 && (
              <p role="status">
                {pick(
                  'Подсветка недоступна для геометрии этой страницы. Проверьте цитату в оригинале.',
                  'Highlight unavailable for this page geometry. Check the source manually.',
                )}
              </p>
            )}
        </Document>
      </div>
    </div>
  )
}
