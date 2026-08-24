import { expect, test } from '@playwright/test'

const documentId = '2f75d3fa-33f4-4a32-8e14-e153e1799a31'
const citation = {
  number: 1,
  chunk_id: '0f092554-5a79-4d9f-bb30-c1a1c9a1e3af',
  page_number: 12,
  quote: 'Максимальный бюджет составляет 1 000 000 рублей.',
  start_char: 10,
  end_char: 58,
}

test('upload, analysis, citation and question flow', async ({ page }) => {
  await page.route('**/api/v1/documents', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, limit: 100, offset: 0 }),
      })
      return
    }
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        document: {
          id: documentId,
          original_filename: 'portfolio-tender.pdf',
          content_type: 'application/pdf',
          size_bytes: 100,
          status: 'uploaded',
          page_count: null,
          error_code: null,
          error_message: null,
          created_at: '2026-08-18T12:00:00Z',
          updated_at: '2026-08-18T12:00:00Z',
        },
        deduplicated: false,
      }),
    })
  })

  await page.route(`**/api/v1/documents/${documentId}`, (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: documentId,
        original_filename: 'portfolio-tender.pdf',
        content_type: 'application/pdf',
        size_bytes: 100,
        status: 'ready',
        page_count: 20,
        error_code: null,
        error_message: null,
        created_at: '2026-08-18T12:00:00Z',
        updated_at: '2026-08-18T12:00:05Z',
      }),
    }),
  )

  await page.route(`**/api/v1/documents/${documentId}/analysis`, (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        document_id: documentId,
        conditions: [
          {
            category: 'budget',
            value: '1 000 000 RUB',
            summary: citation.quote,
            match_score: 0.91,
            citation,
          },
        ],
        risks: [],
        coverage: {
          found_categories: ['budget'],
          missing_categories: ['deadline', 'penalty', 'requirement'],
        },
        retrieval_modes: ['hybrid'],
        disclaimer: 'Не является юридической консультацией.',
      }),
    }),
  )

  await page.route(`**/api/v1/documents/${documentId}/questions`, (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        answer: 'Бюджет составляет 1 000 000 рублей. [1]',
        citations: [citation],
        answer_mode: 'extractive',
        retrieval_mode: 'hybrid',
        grounded: true,
        disclaimer: 'Не является юридической консультацией.',
      }),
    }),
  )

  await page.goto('/')
  await page.getByRole('button', { name: 'Загрузить PDF' }).click()
  await page.getByLabel('Выбрать PDF-файл').setInputFiles({
    name: 'portfolio-tender.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4'),
  })
  await page.getByRole('button', { name: 'Начать анализ' }).click()

  await expect(page).toHaveURL(new RegExp(`/documents/${documentId}`))
  await expect(page.getByRole('heading', { name: 'portfolio-tender.pdf' })).toBeVisible()
  await expect(page.getByText(citation.quote).first()).toBeVisible()

  await page
    .getByRole('button', { name: /Источник · стр. 12/ })
    .first()
    .click()
  await expect(page.getByText('Документ · стр. 12')).toBeVisible()
  await page.getByRole('button', { name: 'Закрыть источник' }).first().click()

  await page.getByRole('button', { name: 'Вопросы' }).click()
  await page.getByLabel('Вопрос по документу').fill('Какой максимальный бюджет?')
  await page.getByRole('button', { name: 'Отправить вопрос' }).click()
  await expect(page.getByText('Подтверждено источниками')).toBeVisible()
})
