import { describe, expect, it } from 'vitest'
import { renderHighlightedPdfText } from './pdfHighlight'

describe('renderHighlightedPdfText', () => {
  it('highlights an exact quote inside a PDF text item', () => {
    expect(
      renderHighlightedPdfText(
        'Оплата производится в течение 30 календарных дней.',
        'в течение 30 календарных дней',
      ),
    ).toBe(
      'Оплата производится <mark class="pdf-citation-highlight">в течение 30 календарных дней</mark>.',
    )
  })

  it('highlights a complete text-layer fragment from a multiline quote', () => {
    expect(
      renderHighlightedPdfText(
        'не позднее 60 календарных дней',
        'Поставка выполняется не позднее 60 календарных дней с даты контракта.',
      ),
    ).toBe('<mark class="pdf-citation-highlight">не позднее 60 календарных дней</mark>')
  })

  it('does not highlight short common fragments and escapes HTML', () => {
    expect(renderHighlightedPdfText('с <риском>', 'условия с риском')).toBe('с &lt;риском&gt;')
  })
})
