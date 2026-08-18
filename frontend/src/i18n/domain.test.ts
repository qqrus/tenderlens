import { describe, expect, it } from 'vitest'
import type { RiskCheckResponse } from '../api/types'
import { localizeRisk } from './domain'

const risk: RiskCheckResponse = {
  rule_id: 'penalty_exposure',
  severity: 'high',
  title: 'Penalty exposure',
  description: 'English backend text',
  recommendation: 'English backend recommendation',
  grounded: true,
  citation: null,
}

describe('localizeRisk', () => {
  it('localizes stable backend rule identifiers without changing grounding', () => {
    const localized = localizeRisk(risk, 'ru')

    expect(localized.title).toBe('Риск штрафов')
    expect(localized.description).toContain('штрафе')
    expect(localized.grounded).toBe(true)
  })
})
