const MIN_FRAGMENT_LENGTH = 6

export function renderHighlightedPdfText(text: string, quote: string | null): string {
  if (!quote?.trim() || !text) return escapeHtml(text)

  const normalizedText = normalizeWhitespace(text)
  const normalizedQuote = normalizeWhitespace(quote)
  if (!normalizedText || !normalizedQuote) return escapeHtml(text)

  const exactMatch = findNormalizedMatch(text, normalizedQuote)
  if (exactMatch) {
    return [
      escapeHtml(text.slice(0, exactMatch.start)),
      `<mark class="pdf-citation-highlight">${escapeHtml(
        text.slice(exactMatch.start, exactMatch.end),
      )}</mark>`,
      escapeHtml(text.slice(exactMatch.end)),
    ].join('')
  }

  if (normalizedText.length >= MIN_FRAGMENT_LENGTH && normalizedQuote.includes(normalizedText)) {
    return `<mark class="pdf-citation-highlight">${escapeHtml(text)}</mark>`
  }

  return escapeHtml(text)
}

function findNormalizedMatch(text: string, normalizedQuote: string) {
  const normalizedChars: string[] = []
  const sourceIndexes: number[] = []
  let previousWasSpace = false

  for (let index = 0; index < text.length; index += 1) {
    const character = text.charAt(index)
    const isSpace = /\s/u.test(character)
    if (isSpace && previousWasSpace) continue
    normalizedChars.push(isSpace ? ' ' : character.toLocaleLowerCase())
    sourceIndexes.push(index)
    previousWasSpace = isSpace
  }

  const normalizedText = normalizedChars.join('').trim()
  const matchStart = normalizedText.indexOf(normalizedQuote)
  if (matchStart < 0) return null

  const leadingWhitespace = normalizedChars.join('').search(/\S/u)
  const mappedStart = matchStart + Math.max(0, leadingWhitespace)
  const mappedEnd = mappedStart + normalizedQuote.length - 1

  return {
    start: sourceIndexes[mappedStart] ?? 0,
    end: (sourceIndexes[mappedEnd] ?? text.length - 1) + 1,
  }
}

function normalizeWhitespace(value: string) {
  return value.replace(/\s+/gu, ' ').trim().toLocaleLowerCase()
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}
