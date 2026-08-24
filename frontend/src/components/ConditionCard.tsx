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
  const hasProminentValue = Boolean(condition.value)

  return (
    <article className="condition-card" data-category={condition.category}>
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
      <div className="condition-answer">
        <span>{pick('Извлечённое значение', 'Extracted value')}</span>
        <strong data-long={!hasProminentValue}>{condition.value ?? condition.summary}</strong>
      </div>
      {hasProminentValue && (
        <blockquote>
          <span>{pick('Контекст из документа', 'Document context')}</span>
          <p>{condition.summary}</p>
        </blockquote>
      )}
      <footer>
        <span>{pick('Проверено по PDF', 'Verified in PDF')}</span>
        <CitationLink citation={condition.citation} onOpen={onCitationOpen} />
      </footer>
    </article>
  )
}
