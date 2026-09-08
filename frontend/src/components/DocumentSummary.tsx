import type { CitationResponse, DocumentAnalysisResponse, DocumentResponse } from '../api/types'
import { localizedDisclaimer } from '../i18n/domain'
import { useLocale } from '../i18n/LocaleContext'
import { ConditionCard } from './ConditionCard'
import { RiskChecklist } from './RiskChecklist'

type Props = {
  document: DocumentResponse
  analysis: DocumentAnalysisResponse
  onCitationOpen: (citation: CitationResponse) => void
}

export function DocumentSummary({ analysis, onCitationOpen }: Props) {
  const { locale, pick } = useLocale()
  const categories = {
    deadline: pick('сроки', 'deadlines'),
    budget: pick('бюджет', 'budget'),
    penalty: pick('штрафы', 'penalties'),
    requirement: pick('требования', 'requirements'),
  }
  // Show actual extracted values, never invented dates or decorative category counts.
  const primary = Object.keys(categories).flatMap((category) => {
    const item = analysis.conditions.find((condition) => condition.category === category)
    return item ? [item] : []
  })
  const risks = analysis.risks.filter((risk) => risk.grounded).slice(0, 2)
  return (
    <div className="summary-stack">
      <header className="summary-heading">
        <span className="page-kicker">{pick('Из документа', 'From the document')}</span>
        <h2>{pick('Главное, с источниками', 'Key findings, with sources')}</h2>
        <p>
          {pick(
            'Выберите цитату, чтобы открыть нужную страницу PDF.',
            'Select a citation to open the matching PDF page.',
          )}
        </p>
      </header>
      <div className="summary-conditions">
        {primary.map((condition) => (
          <ConditionCard
            key={`${condition.category}-${condition.citation.chunk_id}`}
            condition={condition}
            onCitationOpen={onCitationOpen}
          />
        ))}
      </div>
      {analysis.coverage.missing_categories.length > 0 && (
        <section className="coverage-note">
          <div>
            <strong>{pick('Не найдено автоматически', 'Not found automatically')}</strong>
            <p>
              {analysis.coverage.missing_categories
                .map((category) => categories[category])
                .join(', ')}
              .{' '}
              {pick(
                'Это не означает, что условий нет в PDF.',
                'This does not mean these conditions are absent from the PDF.',
              )}
            </p>
          </div>
        </section>
      )}
      {risks.length > 0 && (
        <section className="summary-risks">
          <h2>{pick('На что обратить внимание', 'What needs attention')}</h2>
          <RiskChecklist risks={risks} onCitationOpen={onCitationOpen} />
        </section>
      )}
      <p className="disclaimer">{localizedDisclaimer(locale)}</p>
    </div>
  )
}
