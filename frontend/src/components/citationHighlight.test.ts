import { describe, expect, it } from 'vitest'
import { escapeHtml, findCitationTextItems } from './citationHighlight'

describe('findCitationTextItems', () => {
  it('matches an exact quote split across PDF text items', () => {
    const result = findCitationTextItems(
      [
        { str: 'Общие условия' },
        { str: 'Поставщик уплачивает пеню 0,1%' },
        { str: 'за каждый день просрочки.' },
      ],
      'Поставщик уплачивает пеню 0,1% за каждый день просрочки.',
    )

    expect([...result]).toEqual([1, 2])
  })

  it('ignores whitespace, punctuation and letter case', () => {
    const result = findCitationTextItems(
      [{ str: 'SERVICE restoration' }, { str: 'within 4 hours' }],
      'Service restoration: within 4 hours.',
    )

    expect([...result]).toEqual([0, 1])
  })

  it('does not highlight unrelated text', () => {
    expect(findCitationTextItems([{ str: 'Budget: 100 RUB' }], 'Deadline: tomorrow')).toEqual(
      new Set(),
    )
  })
})

describe('escapeHtml', () => {
  it('keeps PDF text inert when used by the custom renderer', () => {
    expect(escapeHtml('<script>alert("x")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;',
    )
  })
})
