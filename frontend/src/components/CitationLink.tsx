import { ExternalLink } from 'lucide-react'
import type { CitationResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'

type Props = {
  citation: CitationResponse
  onOpen: (citation: CitationResponse) => void
  label?: string
}

export function CitationLink({ citation, onOpen, label }: Props) {
  const { pick } = useLocale()
  return (
    <button className="citation-link" type="button" onClick={() => onOpen(citation)}>
      {label ?? `${pick('Страница', 'Page')} ${citation.page_number}`}
      <ExternalLink aria-hidden="true" />
    </button>
  )
}
