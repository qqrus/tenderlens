import { describe, expect, it } from 'vitest'
import { validatePdf } from './uploadValidation'

describe('validatePdf', () => {
  it('accepts a PDF within the size limit', () => {
    const file = new File(['%PDF-1.4'], 'tender.pdf', { type: 'application/pdf' })
    expect(validatePdf(file)).toBeNull()
  })

  it('rejects unsupported files', () => {
    const file = new File(['hello'], 'tender.txt', { type: 'text/plain' })
    expect(validatePdf(file)).toBe('Поддерживаются только PDF-файлы.')
  })

  it('rejects files larger than 20 MB', () => {
    const file = new File([new Uint8Array(20 * 1024 * 1024 + 1)], 'large.pdf', {
      type: 'application/pdf',
    })
    expect(validatePdf(file)).toBe('Размер файла не должен превышать 20 МБ.')
  })
})
