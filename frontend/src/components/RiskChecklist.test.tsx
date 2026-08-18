import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { RiskCheckResponse } from '../api/types'
import { RiskChecklist } from './RiskChecklist'

const groundedRisk: RiskCheckResponse = {
  rule_id: 'penalty',
  severity: 'high',
  title: 'Высокий штраф',
  description: 'Найден штраф за просрочку.',
  recommendation: 'Проверить срок исполнения.',
  grounded: true,
  citation: {
    number: 1,
    chunk_id: '0f092554-5a79-4d9f-bb30-c1a1c9a1e3af',
    page_number: 12,
    quote: 'Штраф составляет 10%.',
    start_char: 10,
    end_char: 31,
  },
}

const manualRisk: RiskCheckResponse = {
  rule_id: 'missing_budget',
  severity: 'medium',
  title: 'Бюджет требует проверки',
  description: 'Категория не найдена автоматически.',
  recommendation: 'Проверить документ вручную.',
  grounded: false,
  citation: null,
}

describe('RiskChecklist', () => {
  it('separates grounded evidence from manual review warnings', async () => {
    const onCitationOpen = vi.fn()
    render(<RiskChecklist risks={[groundedRisk, manualRisk]} onCitationOpen={onCitationOpen} />)

    expect(screen.getByText('Ручная проверка')).toBeInTheDocument()
    expect(screen.getByText(/Это не доказывает отсутствие условия/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Страница 12/ }))
    expect(onCitationOpen).toHaveBeenCalledWith(groundedRisk.citation)
  })
})
