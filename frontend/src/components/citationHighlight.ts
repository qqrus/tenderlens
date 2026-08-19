type PdfTextItem = {
  str: string
}

type IndexedToken = {
  itemIndex: number
  value: string
}

const TOKEN_PATTERN = /[\p{L}\p{N}]+/gu

export function findCitationTextItems(items: PdfTextItem[], quote: string): Set<number> {
  const quoteTokens = tokenize(quote)
  if (!quoteTokens.length) return new Set()

  const pageTokens = items.flatMap((item, itemIndex) =>
    tokenize(item.str).map((value) => ({ itemIndex, value })),
  )
  if (pageTokens.length < quoteTokens.length) return new Set()

  for (let start = 0; start <= pageTokens.length - quoteTokens.length; start += 1) {
    if (matchesAt(pageTokens, quoteTokens, start)) {
      return new Set(
        pageTokens.slice(start, start + quoteTokens.length).map((token) => token.itemIndex),
      )
    }
  }
  return new Set()
}

export function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function tokenize(value: string) {
  return Array.from(value.toLocaleLowerCase().matchAll(TOKEN_PATTERN), (match) => match[0])
}

function matchesAt(pageTokens: IndexedToken[], quoteTokens: string[], start: number) {
  return quoteTokens.every((token, offset) => pageTokens[start + offset]?.value === token)
}
