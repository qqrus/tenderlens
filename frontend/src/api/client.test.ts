import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadDocumentFile, getDocumentFileUrl } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('getDocumentFileUrl', () => {
  it('builds the persistent PDF endpoint from the configured API base URL', () => {
    expect(getDocumentFileUrl('document-id')).toBe(
      'http://localhost:8000/api/v1/documents/document-id/file',
    )
  })
})

describe('downloadDocumentFile', () => {
  it('downloads a PDF through the checked API client', async () => {
    const pdf = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/pdf' }),
        blob: vi.fn().mockResolvedValue(pdf),
      } satisfies Partial<Response>),
    )

    const downloaded = await downloadDocumentFile('document-id')

    expect(downloaded).toBe(pdf)
    expect(downloaded.type).toBe('application/pdf')
    expect(downloaded.size).toBe(pdf.size)
  })
})
