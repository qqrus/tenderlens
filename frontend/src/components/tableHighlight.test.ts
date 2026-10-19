import { describe, expect, it } from 'vitest'
import type { TableAnswerResponse } from '../api/types'
import { tableRegions } from './tableHighlight'

const cell = { text: 'Value', box: { x0: 10, top: 20, x1: 40, bottom: 60 } }
const answer: TableAnswerResponse = {
  document_id: 'doc',
  source_sha256: 'a'.repeat(64),
  page_width: 100,
  page_height: 200,
  evidence: { page_number: 2, row_label: cell, column_header: cell, value: cell },
}
describe('table geometry', () => {
  it('maps all three PDF regions to scale-independent percentages', () => {
    const regions = tableRegions(answer, 2, 100, 200)
    expect(regions).toHaveLength(3)
    expect(regions[2]).toEqual({
      role: 'value',
      left: '10%',
      top: '10%',
      width: '30%',
      height: '20%',
    })
  })
  it('does not carry highlights to another page', () =>
    expect(tableRegions(answer, 1, 100, 200)).toEqual([]))
  it('refuses mismatched page dimensions and unsupported transforms', () => {
    expect(tableRegions(answer, 2, 200, 100)).toEqual([])
    expect(tableRegions(answer, 2, 0, 0)).toEqual([])
  })
  it('rejects invalid and out-of-bounds boxes', () => {
    const broken = structuredClone(answer)
    broken.evidence.value = structuredClone(cell)
    broken.evidence.row_label = structuredClone(cell)
    broken.evidence.value.box.x1 = 101
    expect(tableRegions(broken, 2, 100, 200)).toHaveLength(2)
    broken.evidence.row_label.box.top = Number.NaN
    expect(tableRegions(broken, 2, 100, 200)).toHaveLength(1)
  })
})
