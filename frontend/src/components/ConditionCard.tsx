import { Banknote, CalendarClock, FileCheck2, Gavel } from 'lucide-react'
import type { CitationResponse, ExtractedConditionResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'
import { CitationLink } from './CitationLink'

const meta = {
  deadline: { label: 'Срок', icon: CalendarClock },
  budget: { label: 'Бюджет', icon: Banknote },
  penalty: { label: 'Штраф', icon: Gavel },
  requirement: { label: 'Требование', icon: FileCheck2 },
} as const

type Props = {
  condition: ExtractedConditionResponse
  onCitationOpen: (citation: CitationResponse) => void
}

export function ConditionCard({ condition, onCitationOpen }: Props) {
  const { pick } = useLocale()
  const { label: russianLabel, icon: Icon } = meta[condition.category]
  const englishLabels = {
    deadline: 'Deadline',
    budget: 'Budget',
    penalty: 'Penalty',
    requirement: 'Requirement',
  }
  const label = pick(russianLabel, englishLabels[condition.category])

  return (
    <article className="condition-card">
      <header>
        <span className="condition-icon">
          <Icon aria-hidden="true" />
        </span>
        <span className="condition-category">{label}</span>
        <span
          className="match-score"
          title={pick(
            'Технический показатель совпадения правила, не юридическая оценка',
            'Technical rule match score, not a legal assessment',
          )}
        >
          {pick('Правило', 'Rule')} {Math.round(condition.match_score * 100)}%
        </span>
      </header>
      <p>{condition.summary}</p>
      <footer>
        <span>{pick('Источник подтверждён', 'Source verified')}</span>
        <CitationLink citation={condition.citation} onOpen={onCitationOpen} />
      </footer>
    </article>
  )
}
