import { AlertTriangle, CircleCheck, ClipboardCheck } from 'lucide-react'
import type { CitationResponse, RiskCheckResponse } from '../api/types'
import { localizeRisk } from '../i18n/domain'
import { useLocale } from '../i18n/LocaleContext'
import { CitationLink } from './CitationLink'
import { EmptyState } from './EmptyState'
import { RiskBadge } from './RiskBadge'

type Props = {
  risks: RiskCheckResponse[]
  onCitationOpen: (citation: CitationResponse) => void
}

export function RiskChecklist({ risks, onCitationOpen }: Props) {
  const { locale, pick } = useLocale()
  if (!risks.length)
    return (
      <EmptyState
        message={pick(
          'Автоматическая проверка не сформировала риски.',
          'The automated review found no risk signals.',
        )}
      />
    )

  return (
    <div className="risk-list">
      {risks.map((rawRisk) => {
        const risk = localizeRisk(rawRisk, locale)
        return (
          <article className="risk-card" key={risk.rule_id} data-grounded={risk.grounded}>
            <div className="risk-card-marker">
              {risk.grounded ? (
                <AlertTriangle aria-hidden="true" />
              ) : (
                <ClipboardCheck aria-hidden="true" />
              )}
            </div>
            <div className="risk-card-content">
              <header>
                <div>
                  <RiskBadge severity={risk.severity} />
                  {!risk.grounded && (
                    <span className="manual-badge">{pick('Ручная проверка', 'Manual review')}</span>
                  )}
                </div>
                {risk.grounded && risk.citation && (
                  <CitationLink citation={risk.citation} onOpen={onCitationOpen} />
                )}
              </header>
              <h3>{risk.title}</h3>
              <p>{risk.description}</p>
              <div className="recommendation">
                <CircleCheck aria-hidden="true" />
                <span>
                  <strong>{pick('Что проверить:', 'What to check:')}</strong> {risk.recommendation}
                </span>
              </div>
              {!risk.grounded && (
                <p className="manual-note">
                  {pick(
                    'Категория не найдена автоматически. Это не доказывает отсутствие условия в документе.',
                    'The category was not found automatically. This does not prove that the condition is absent.',
                  )}
                </p>
              )}
            </div>
          </article>
        )
      })}
    </div>
  )
}
