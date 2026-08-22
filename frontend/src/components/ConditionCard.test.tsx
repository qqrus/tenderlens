import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ExtractedConditionResponse } from '../api/types'
import { LocaleProvider } from '../i18n/LocaleContext'
import { ConditionCard } from './ConditionCard'

const condition: ExtractedConditionResponse = {
  category: 'deadline',
  value: '17 ноября 2026 года в 15:15',
  summary: 'Срок подачи заявки — 17 ноября 2026 года в 15:15.',
  match_score: 0.91,
  citation: {
    number: 1,
    chunk_id: 'c816314d-3f0c-4264-bf27-737db2a0de54',
    page_number: 7,
    quote: 'Срок подачи заявки — 17 ноября 2026 года в 15:15.',
    start_char: 12,
    end_char: 65,
  },
}

describe('ConditionCard', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
      },
    })
  })

  it('shows the extracted value more prominently than its source context', () => {
    render(
      <LocaleProvider>
        <ConditionCard condition={condition} onCitationOpen={vi.fn()} />
      </LocaleProvider>,
    )

    expect(screen.getByText('Извлечённое значение')).toBeInTheDocument()
    expect(screen.getByText('17 ноября 2026 года в 15:15').tagName).toBe('STRONG')
    expect(screen.getByText(condition.summary)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /страница 7/i })).toBeInTheDocument()
  })
})
