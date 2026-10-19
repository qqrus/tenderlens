import type { TableAnswerResponse } from '../api/types'

export function tableRegions(
  answer: TableAnswerResponse,
  page: number,
  width: number,
  height: number,
) {
  if (
    answer.evidence.page_number !== page ||
    Math.abs(answer.page_width - width) > 0.5 ||
    Math.abs(answer.page_height - height) > 0.5
  )
    return []
  return (['row_label', 'column_header', 'value'] as const).flatMap((role) => {
    const b = answer.evidence[role].box
    if (
      ![b.x0, b.top, b.x1, b.bottom, width, height].every(Number.isFinite) ||
      width <= 0 ||
      height <= 0 ||
      b.x0 < 0 ||
      b.top < 0 ||
      b.x1 > width ||
      b.bottom > height ||
      b.x1 <= b.x0 ||
      b.bottom <= b.top
    )
      return []
    return [
      {
        role,
        left: `${(100 * b.x0) / width}%`,
        top: `${(100 * b.top) / height}%`,
        width: `${(100 * (b.x1 - b.x0)) / width}%`,
        height: `${(100 * (b.bottom - b.top)) / height}%`,
      },
    ]
  })
}

export async function pdfSha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export const tableColors = { row_label: '#eab308', column_header: '#a78bfa', value: '#3b82f6' }
