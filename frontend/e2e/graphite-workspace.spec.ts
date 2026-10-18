import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const A = '2f75d3fa-33f4-4a32-8e14-e153e1799a31'
const B = '2f75d3fa-33f4-4a32-8e14-e153e1799a32'
const fixture = (id: string) =>
  resolve(`../output/pdf/tenderlens-eval-v2/${id === A ? 'ru-servers-001' : 'ru-office-002'}.pdf`)
const quote = 'Цена предложения не может превышать 18 400 000 рублей, включая НДС.'
const meta = (id: string) => ({
  id,
  original_filename: id === A ? 'Учебный пример — серверы.pdf' : 'Учебный пример — ремонт.pdf',
  status: 'ready',
  content_type: 'application/pdf',
  size_bytes: 50000,
  page_count: 20,
  extraction_method: 'native',
  ocr_page_count: 0,
  error_code: null,
  error_message: null,
  created_at: '2026-09-08T12:00:00Z',
  updated_at: '2026-09-08T12:00:00Z',
})

async function mockApi(page: Page, analysisFails = false) {
  const fileRequests: string[] = []
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const tail = path.split('/').at(-1)
    const id = path.includes(B) ? B : A
    if (tail === 'file') {
      fileRequests.push(id)
      return route.fulfill({ contentType: 'application/pdf', body: readFileSync(fixture(id)) })
    }
    let data: unknown
    if (tail === 'documents')
      data =
        route.request().method() === 'POST'
          ? { document: meta(A), deduplicated: false }
          : { items: [meta(A), meta(B)], total: 2, limit: 100, offset: 0 }
    else if (tail === 'analysis') {
      if (analysisFails)
        return route.fulfill({
          status: 503,
          json: { error: { code: 'unavailable', message: 'Analysis unavailable' } },
        })
      data = {
        document_id: id,
        conditions: [
          {
            category: 'budget',
            value: '18 400 000 ₽',
            summary: quote,
            match_score: 0.9,
            citation: {
              number: 1,
              chunk_id: id,
              page_number: 4,
              quote,
              start_char: 0,
              end_char: quote.length,
            },
          },
        ],
        risks: [],
        coverage: {
          found_categories: ['budget'],
          missing_categories: ['deadline', 'penalty', 'requirement'],
        },
        retrieval_modes: ['hybrid'],
        disclaimer: 'Учебный пример',
      }
    } else if (tail === 'questions')
      data = {
        answer: 'Недостаточно подтверждений.',
        citations: [],
        answer_mode: 'extractive',
        retrieval_mode: 'hybrid',
        grounded: false,
        disclaimer: 'Учебный пример',
      }
    else data = meta(id)
    return route.fulfill({ json: data })
  })
  return fileRequests
}

test('upload A then open B renders the correct PDF, including after refresh', async ({ page }) => {
  const requests = await mockApi(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Загрузить PDF', exact: true }).click()
  await page.getByLabel('Выбрать PDF-файл').setInputFiles(fixture(A))
  await page.getByRole('button', { name: 'Начать анализ' }).click()
  await expect(page.locator('.react-pdf__Page__textContent')).toContainText('TL-RU-2026-001')
  await page.getByRole('link', { name: 'TenderLens — документы', exact: true }).click()
  await page.getByText(meta(B).original_filename, { exact: true }).click()
  await expect(page.locator('.react-pdf__Page__textContent')).toContainText('TL-RU-2026-002')
  expect(requests).toContain(B)
  await expect(page.locator('.react-pdf__Page__textContent')).not.toContainText('TL-RU-2026-001')
  await page.reload()
  await expect(page.locator('.react-pdf__Page__textContent')).toContainText('TL-RU-2026-002')
})

test('mobile layout, source modal focus, Escape and English labels', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page)
  await page.goto(`/documents/${A}`)
  await expect(page.locator('.react-pdf__Page__textContent')).toContainText('TL-RU-2026-001')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Страница 4', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Панель источника' })).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Закрыть источник', exact: true }).first(),
  ).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Страница 4', exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'EN', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Questions', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
})

test('analysis failure does not block PDF or questions', async ({ page }) => {
  await mockApi(page, true)
  await page.goto(`/documents/${A}`)
  await expect(page.getByRole('heading', { name: 'Анализ временно недоступен' })).toBeVisible()
  await expect(page.locator('.react-pdf__Page__textContent')).toContainText('TL-RU-2026-001')
  await page.getByRole('button', { name: 'Вопросы', exact: true }).click()
  await page.getByLabel('Вопрос по документу').fill('Какие условия?')
  await page.getByRole('button', { name: 'Отправить вопрос' }).click()
  await expect(page.getByText('Недостаточно подтверждений.', { exact: true })).toBeVisible()
})

test('upload dialog contains focus and returns it on Escape', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  const trigger = page.getByRole('button', { name: 'Загрузить PDF', exact: true })
  await trigger.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Shift+Tab')
  expect(
    await page.getByRole('dialog').evaluate((node) => node.contains(document.activeElement)),
  ).toBe(true)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(trigger).toBeFocused()
})
