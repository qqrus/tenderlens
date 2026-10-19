import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { GeometrySnapshot, TableAnswerResponse } from '../src/api/types'

// Actual coordinates extracted from a tracked synthetic PDF; only HTTP is mocked.
const file = resolve('../output/pdf/tenderlens-eval-v2/ru-servers-001.pdf')
const bytes = readFileSync(file)
const hash = createHash('sha256').update(bytes).digest('hex')
const tables = JSON.parse(
  execFileSync(
    'uv',
    [
      'run',
      '--extra',
      'tables',
      'python',
      '-c',
      'import json,sys; from pathlib import Path; from tenderlens.ingestion.table_geometry import inspect_page_tables; print(json.dumps([t.model_dump() for t in inspect_page_tables(Path(sys.argv[1]), [4])]))',
      file,
    ],
    { cwd: resolve('..'), encoding: 'utf8' },
  ),
) as NonNullable<GeometrySnapshot['tables']>
const index = tables.findIndex((t) => t.rows[0]?.[1]?.text === 'Сведения')
const table = tables[index]!
const id = '2f75d3fa-33f4-4a32-8e14-e153e1799a31'
const answer: TableAnswerResponse = {
  document_id: id,
  source_sha256: hash,
  page_width: table.page_width,
  page_height: table.page_height,
  evidence: {
    page_number: table.page_number,
    row_label: table.rows[1]![0]!,
    column_header: table.rows[0]![1]!,
    value: table.rows[1]![1]!,
  },
}

for (const mismatched of [false, true]) {
  test(`table lookup and PDF overlay: source mismatch=${mismatched}`, async ({ page }) => {
    await page.route('**/api/v1/**', async (route) => {
      const tail = new URL(route.request().url()).pathname.split('/').at(-1)
      if (tail === 'file') return route.fulfill({ contentType: 'application/pdf', body: bytes })
      if (tail === 'tables')
        return route.fulfill({ json: { status: 'ready', source_sha256: hash, tables } })
      if (tail === 'table-answer') {
        expect(route.request().postDataJSON()).toEqual({
          source_sha256: hash,
          table_index: index,
          row_label: answer.evidence.row_label.text,
          column_header: answer.evidence.column_header.text,
        })
        return route.fulfill({
          json: { ...answer, source_sha256: mismatched ? 'b'.repeat(64) : hash },
        })
      }
      if (tail === 'analysis')
        return route.fulfill({ status: 503, json: { error: { code: 'unavailable' } } })
      return route.fulfill({
        json: {
          id,
          original_filename: 'Synthetic test.pdf',
          status: 'ready',
          page_count: 20,
          ocr_page_count: 0,
          updated_at: '2026-10-19T12:00:00Z',
        },
      })
    })
    await page.goto(`/documents/${id}`)
    await page.getByRole('button', { name: 'Вопросы', exact: true }).click()
    await page.getByText('Ответ из таблицы · эксперимент', { exact: true }).click()
    await page.getByLabel('Таблица', { exact: true }).selectOption(String(index))
    await page.getByLabel('Строка', { exact: true }).selectOption(answer.evidence.row_label.text)
    await page
      .getByLabel('Столбец', { exact: true })
      .selectOption(answer.evidence.column_header.text)
    await page.getByRole('button', { name: 'Прочитать ячейку' }).click()
    await expect(page.locator('.table-answer > p')).toHaveText(answer.evidence.value.text)
    await page.getByRole('button', { name: /Показать три области/ }).click()
    if (mismatched) {
      await expect(page.getByRole('status').filter({ hasText: 'Подсветка скрыта' })).toBeVisible()
      await expect(page.locator('.pdf-geometry-box')).toHaveCount(0)
      return
    }
    await expect(page.locator('.pdf-geometry-box')).toHaveCount(3)
    const assertAlignment = async () => {
      const canvas = await page.locator('.react-pdf__Page__canvas').boundingBox()
      const box = await page.locator('[data-table-role="value"]').boundingBox()
      expect(canvas).toBeTruthy()
      expect(box).toBeTruthy()
      const expected = answer.evidence.value.box
      expect(
        Math.abs(box!.x - canvas!.x - (expected.x0 / table.page_width) * canvas!.width),
      ).toBeLessThan(2)
      expect(
        Math.abs(box!.y - canvas!.y - (expected.top / table.page_height) * canvas!.height),
      ).toBeLessThan(2)
    }
    await assertAlignment()
    await page.screenshot({ path: 'test-results/table-evidence-desktop.png', fullPage: true })
    await page.getByRole('button', { name: 'Следующая страница' }).click()
    await expect(page.locator('.pdf-geometry-box')).toHaveCount(0)
    await page.getByRole('button', { name: 'Предыдущая страница' }).click()
    await expect(page.locator('.pdf-geometry-box')).toHaveCount(3)
    await page.setViewportSize({ width: 390, height: 844 })
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      .toBe(true)
    await expect
      .poll(
        async () =>
          (await page.locator('.react-pdf__Page__canvas').boundingBox())?.width ?? Infinity,
      )
      .toBeLessThan(390)
    await assertAlignment()
    await page.screenshot({ path: 'test-results/table-evidence-mobile.png', fullPage: true })
  })
}
