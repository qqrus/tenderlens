import { describe, expect, it } from 'vitest'
import { datasetSplits, evaluationModels, experimentMeta } from './mlReport'

describe('ML report data', () => {
  it('matches the checked-in v2 experiment summary', () => {
    expect(datasetSplits.reduce((total, split) => total + split.queries, 0)).toBe(
      experimentMeta.queries,
    )
    expect(datasetSplits.reduce((total, split) => total + split.pairs, 0)).toBe(
      experimentMeta.pairs,
    )
    expect(evaluationModels.find((model) => model.id === 'tuned')?.hitAt1).toBe(0.989583)
  })

  it('shows an improvement over both baselines without exceeding metric bounds', () => {
    const lexical = evaluationModels[0]!
    const base = evaluationModels[1]!
    const tuned = evaluationModels[2]!
    expect(tuned.hitAt1).toBeGreaterThan(base.hitAt1)
    expect(base.hitAt1).toBeGreaterThan(lexical.hitAt1)
    for (const model of evaluationModels) {
      expect(model.hitAt1).toBeGreaterThanOrEqual(0)
      expect(model.hitAt3).toBeLessThanOrEqual(1)
      expect(model.mrr).toBeLessThanOrEqual(1)
    }
  })
})
