import type {
  GeometrySnapshot,
  TableAnswerRequest,
  TableAnswerResponse,
  AnswerResponse,
  DocumentAnalysisResponse,
  DocumentListResponse,
  DocumentResponse,
  DocumentUploadResponse,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

type ErrorPayload = {
  error?: {
    code?: string
    message?: string
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function requestResponse(path: string, init?: RequestInit): Promise<Response> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(
      'Не удалось связаться с TenderLens API. Проверьте, что backend запущен.',
      0,
      'backend_unavailable',
    )
  }

  if (!response.ok) {
    let payload: ErrorPayload | undefined
    try {
      payload = (await response.json()) as ErrorPayload
    } catch {
      payload = undefined
    }

    const code = payload?.error?.code ?? `http_${response.status}`
    const fallback =
      response.status === 404
        ? 'Запрошенные данные пока недоступны.'
        : 'Не удалось выполнить запрос. Попробуйте ещё раз.'

    throw new ApiError(payload?.error?.message ?? fallback, response.status, code)
  }

  return response
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await requestResponse(path, init)
  return (await response.json()) as T
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<DocumentUploadResponse>('/api/v1/documents', {
    method: 'POST',
    body: form,
  })
}

export function getDocument(documentId: string): Promise<DocumentResponse> {
  return request<DocumentResponse>(`/api/v1/documents/${documentId}`)
}

export function getDocumentTables(documentId: string): Promise<GeometrySnapshot> {
  return request(`/api/v1/documents/${documentId}/tables`)
}

export function answerTableCell(
  documentId: string,
  body: TableAnswerRequest,
): Promise<TableAnswerResponse> {
  return request(`/api/v1/documents/${documentId}/table-answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function listDocuments(limit = 20, offset = 0): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return request<DocumentListResponse>(`/api/v1/documents?${params}`)
}

export function getDocumentFileUrl(documentId: string): string {
  return `${API_BASE_URL}/api/v1/documents/${encodeURIComponent(documentId)}/file`
}

export async function downloadDocumentFile(documentId: string): Promise<Blob> {
  const response = await requestResponse(`/api/v1/documents/${encodeURIComponent(documentId)}/file`)
  const contentType = response.headers.get('content-type')
  if (contentType && !contentType.toLowerCase().includes('application/pdf')) {
    throw new ApiError('Сервер вернул файл неподдерживаемого формата.', 500, 'invalid_pdf_response')
  }
  const blob = await response.blob()
  return blob
}

export function analyzeDocument(documentId: string): Promise<DocumentAnalysisResponse> {
  return request<DocumentAnalysisResponse>(`/api/v1/documents/${documentId}/analysis`, {
    method: 'POST',
  })
}

export function askQuestion(documentId: string, question: string): Promise<AnswerResponse> {
  return request<AnswerResponse>(`/api/v1/documents/${documentId}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export function humanizeError(error: unknown, locale: 'ru' | 'en' = 'ru'): string {
  const pick = (ru: string, en: string) => (locale === 'ru' ? ru : en)
  if (error instanceof ApiError) {
    if (error.code === 'geometry_source_mismatch')
      return pick(
        'Источник таблицы изменился. Обновите страницу и выберите ячейку снова.',
        'The table source changed. Refresh the page and select the cell again.',
      )
    if (error.code === 'table_not_ready')
      return pick(
        'Геометрия таблиц ещё не готова или недоступна для этого документа.',
        'Table geometry is not ready or is unavailable for this document.',
      )
    if (error.code === 'table_not_found')
      return pick('Таблица не найдена. Обновите страницу.', 'Table not found. Refresh the page.')
    if (error.code === 'no_extractable_text') {
      return pick(
        'Не удалось извлечь или распознать текст. Проверьте качество страниц PDF.',
        'Text could not be extracted or recognized. Check the PDF page quality.',
      )
    }
    if (error.code === 'file_too_large') {
      return pick('Файл превышает допустимый размер 20 МБ.', 'The file exceeds the 20 MB limit.')
    }
    if (error.code === 'invalid_pdf' || error.code === 'unsupported_file') {
      return pick('Выберите корректный PDF-файл.', 'Choose a valid PDF file.')
    }
    if (error.code === 'backend_unavailable')
      return pick(
        'Не удалось связаться с TenderLens API. Проверьте, что backend запущен.',
        'Could not connect to TenderLens API. Check that the backend is running.',
      )
    if (locale === 'en') return 'The request could not be completed. Please try again.'
    return error.message
  }
  return pick(
    'Произошла непредвиденная ошибка. Попробуйте ещё раз.',
    'An unexpected error occurred. Please try again.',
  )
}
