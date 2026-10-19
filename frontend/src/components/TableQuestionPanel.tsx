import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, answerTableCell, getDocumentTables, humanizeError } from '../api/client'
import type { GeometrySnapshot, TableAnswerResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'
import './tableEvidence.css'

export function TableQuestionPanel({
  documentId,
  onEvidenceOpen,
}: {
  documentId: string
  onEvidenceOpen: (answer: TableAnswerResponse) => void
}) {
  const { locale, pick } = useLocale()
  const query = useQuery({
    queryKey: ['tables', documentId],
    queryFn: () => getDocumentTables(documentId),
    retry: 1,
  })
  return (
    <details className="table-question-panel">
      <summary>{pick('Ответ из таблицы · эксперимент', 'Table lookup · experimental')}</summary>
      <p>
        {pick(
          'Выберите строку и столбец. Это точное чтение ячейки, а не ответ модели на свободный вопрос. Поддерживаются простые таблицы с границами и одной строкой заголовков.',
          'Choose a row and column. This is a direct cell lookup, not a model answering a free-form question. Only simple bordered tables with one header row are supported.',
        )}
      </p>
      {query.isPending ? (
        <p>{pick('Загружаем таблицы…', 'Loading tables…')}</p>
      ) : query.isError ? (
        <div role="alert">
          {humanizeError(query.error, locale)}{' '}
          <button type="button" onClick={() => void query.refetch()}>
            {pick('Повторить', 'Retry')}
          </button>
        </div>
      ) : query.data.status !== 'ready' ? (
        <p>
          {pick(
            'Геометрия таблиц для этого файла недоступна. Она извлекается только при новой загрузке с включённым TABLE_GEOMETRY_ENABLED. Старые файлы автоматически не переобрабатываются; сканы пока не поддерживаются.',
            'Table geometry is unavailable for this file. It is extracted on new uploads with TABLE_GEOMETRY_ENABLED enabled. Existing files are not automatically reprocessed; scans are not supported yet.',
          )}
        </p>
      ) : !query.data.tables?.length ? (
        <p>{pick('Таблицы с границами не найдены.', 'No bordered tables found.')}</p>
      ) : (
        <TableSelection
          key={query.data.source_sha256}
          snapshot={query.data}
          documentId={documentId}
          onEvidenceOpen={onEvidenceOpen}
        />
      )}
    </details>
  )
}

function TableSelection({
  snapshot,
  documentId,
  onEvidenceOpen,
}: {
  snapshot: GeometrySnapshot
  documentId: string
  onEvidenceOpen: (answer: TableAnswerResponse) => void
}) {
  const { locale, pick } = useLocale()
  const [tableIndex, setTableIndex] = useState(0)
  const [row, setRow] = useState('')
  const [column, setColumn] = useState('')
  const [answer, setAnswer] = useState<TableAnswerResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const tables = snapshot.tables ?? []
  const table = tables[tableIndex]
  const rows = [
    ...new Set(
      (table?.rows ?? [])
        .slice(1)
        .map((r) => r[0]?.text)
        .filter((text): text is string => Boolean(text?.trim())),
    ),
  ]
  const columns = [
    ...new Set(
      (table?.rows[0] ?? [])
        .slice(1)
        .map((c) => c?.text)
        .filter((text): text is string => Boolean(text?.trim())),
    ),
  ]
  const reset = () => {
    setAnswer(null)
    setError(null)
  }
  const submit = async () => {
    setPending(true)
    reset()
    try {
      setAnswer(
        await answerTableCell(documentId, {
          source_sha256: snapshot.source_sha256,
          table_index: tableIndex,
          row_label: row,
          column_header: column,
        }),
      )
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.code === 'table_cell_ambiguous'
          ? pick(
              'Однозначная непустая ячейка не найдена. Проверьте исходную таблицу: возможны повторяющиеся заголовки или объединённые ячейки.',
              'No unique non-empty cell found. Check the source for duplicate headers or merged cells.',
            )
          : humanizeError(cause, locale),
      )
    } finally {
      setPending(false)
    }
  }
  return (
    <div>
      <fieldset disabled={pending} className="table-controls">
        <label>
          {pick('Таблица', 'Table')}
          <select
            aria-label={pick('Таблица', 'Table')}
            value={tableIndex}
            onChange={(e) => {
              setTableIndex(Number(e.target.value))
              setRow('')
              setColumn('')
              reset()
            }}
          >
            {tables.map((t, index) => (
              <option value={index} key={index}>
                {index + 1} · {pick('стр.', 'p.')} {t.page_number}
              </option>
            ))}
          </select>
        </label>
        <label>
          {pick('Строка', 'Row')}
          <select
            aria-label={pick('Строка', 'Row')}
            value={row}
            onChange={(e) => {
              setRow(e.target.value)
              reset()
            }}
          >
            <option value="">{pick('Выберите строку', 'Select a row')}</option>
            {rows.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <label>
          {pick('Столбец', 'Column')}
          <select
            aria-label={pick('Столбец', 'Column')}
            value={column}
            onChange={(e) => {
              setColumn(e.target.value)
              reset()
            }}
          >
            <option value="">{pick('Выберите столбец', 'Select a column')}</option>
            {columns.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="secondary-button"
          disabled={!row || !column}
          onClick={() => void submit()}
        >
          {pending ? pick('Проверяем…', 'Checking…') : pick('Прочитать ячейку', 'Read cell')}
        </button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {answer && (
        <div className="table-answer" aria-live="polite">
          <span>
            {answer.evidence.row_label.text} · {answer.evidence.column_header.text}
          </span>
          <p>{answer.evidence.value.text}</p>
          <button className="secondary-button" type="button" onClick={() => onEvidenceOpen(answer)}>
            {pick('Показать три области в PDF', 'Show three regions in PDF')} · {pick('стр.', 'p.')}{' '}
            {answer.evidence.page_number}
          </button>
          <small>
            {pick(
              'Текст ячейки без интерпретации. Проверьте заголовки, единицы и примечания в оригинале.',
              'Cell text without interpretation. Verify headers, units and footnotes in the original.',
            )}
          </small>
        </div>
      )}
    </div>
  )
}
