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
      vi
        .fn()
        .mockResolvedValue(
          new Response(pdf, { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
        ),
    )

    await expect(downloadDocumentFile('document-id')).resolves.toEqual(pdf)
  })
})
