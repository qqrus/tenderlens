import {
  AlertTriangle,
  Banknote,
  CalendarClock,
  Check,
  FileCheck2,
  Gavel,
  ShieldCheck,
} from 'lucide-react'
import type {
  CitationResponse,
  ConditionCategory,
  DocumentAnalysisResponse,
  DocumentResponse,
  ExtractedConditionResponse,
} from '../api/types'
import { localizeRisk, localizedDisclaimer } from '../i18n/domain'
import { useLocale } from '../i18n/LocaleContext'
import { CitationLink } from './CitationLink'

const categoryMeta: Record<
  ConditionCategory,
  { label: string; plural: string; icon: typeof CalendarClock }
> = {
  deadline: { label: 'Сроки', plural: 'сроков', icon: CalendarClock },
  budget: { label: 'Бюджет', plural: 'финансовых условий', icon: Banknote },
  penalty: { label: 'Штрафы', plural: 'условий ответственности', icon: Gavel },
  requirement: { label: 'Требования', plural: 'требований', icon: FileCheck2 },
}

const categories: ConditionCategory[] = ['deadline', 'budget', 'penalty', 'requirement']
const englishCategoryMeta: Record<ConditionCategory, { label: string; plural: string }> = {
  deadline: { label: 'Deadlines', plural: 'deadlines' },
  budget: { label: 'Budget', plural: 'financial conditions' },
  penalty: { label: 'Penalties', plural: 'liability conditions' },
  requirement: { label: 'Requirements', plural: 'requirements' },
}

type Props = {
  document: DocumentResponse
  analysis: DocumentAnalysisResponse
  onCitationOpen: (citation: CitationResponse) => void
}

export function DocumentSummary({ document, analysis, onCitationOpen }: Props) {
  const { locale, pick } = useLocale()
  const groundedRisks = analysis.risks.filter((risk) => risk.grounded)
  const highRisks = groundedRisks.filter((risk) => risk.severity === 'high')
  const citationCount = new Set([
    ...analysis.conditions.map((condition) => condition.citation.chunk_id),
    ...groundedRisks.flatMap((risk) => (risk.citation ? [risk.citation.chunk_id] : [])),
  ]).size

  return (
    <div className="summary-stack">
      <section className="analysis-overview">
        <div>
          <span className="page-kicker">{pick('Карта решения', 'Decision map')}</span>
          <h1>{document.original_filename}</h1>
          <p>
            {pick(
              'Все выводы ниже связаны с конкретными страницами исходного PDF.',
              'Every finding below is linked to a specific page in the source PDF.',
            )}
          </p>
        </div>
        <div className="overview-metrics" aria-label={pick('Итоги анализа', 'Analysis summary')}>
          <div>
            <strong>{analysis.conditions.length}</strong>
            <span>{pick('условий', 'conditions')}</span>
          </div>
          <div>
            <strong>{groundedRisks.length}</strong>
            <span>{pick('рисков с источником', 'grounded risks')}</span>
          </div>
          <div>
            <strong>{citationCount}</strong>
            <span>{pick('цитат', 'citations')}</span>
          </div>
        </div>
      </section>

      <section className="analysis-flow" aria-label={pick('Этапы обработки', 'Processing stages')}>
        <FlowStep
          label={pick('PDF загружен', 'PDF uploaded')}
          value={formatDate(document.created_at, locale)}
          complete
        />
        <FlowStep
          label={pick('Текст извлечён', 'Text extracted')}
          value={
            document.page_count
              ? `${document.page_count} ${pick('страниц', 'pages')}`
              : pick('готово', 'ready')
          }
          complete
        />
        <FlowStep
          label={pick('Условия сопоставлены', 'Conditions matched')}
          value={`${analysis.conditions.length} ${pick('найдено', 'found')}`}
          complete
        />
        <FlowStep
          label={pick('Источники готовы', 'Sources ready')}
          value={`${citationCount} ${pick('ссылок', 'links')}`}
          complete
        />
      </section>

      <section className="evidence-map-section" aria-labelledby="evidence-map-title">
        <div className="section-heading">
          <div>
            <span className="page-kicker">{pick('Структура документа', 'Document structure')}</span>
            <h2 id="evidence-map-title">{pick('Карта доказательств', 'Evidence map')}</h2>
          </div>
          <span className="technical-note">
            {pick('Поиск', 'Search')} · {analysis.retrieval_modes.join(' + ')}
          </span>
        </div>
        <div className="evidence-map">
          <div className="map-rings" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
          <div className="map-core">
            <span>
              <ShieldCheck aria-hidden="true" />
            </span>
            <small>{pick('Анализ', 'Analysis')}</small>
            <strong>{analysis.coverage.found_categories.length}/4</strong>
            <p>{pick('категории найдены', 'categories found')}</p>
          </div>
          {categories.map((category) => {
            const conditions = analysis.conditions.filter(
              (condition) => condition.category === category,
            )
            return (
              <EvidenceNode
                key={category}
                category={category}
                conditions={conditions}
                onCitationOpen={onCitationOpen}
                locale={locale}
                pick={pick}
              />
            )
          })}
        </div>
      </section>

      <section className="risk-preview" aria-labelledby="risk-preview-title">
        <div className="section-heading">
          <div>
            <span className="page-kicker">{pick('Контрольные сигналы', 'Control signals')}</span>
            <h2 id="risk-preview-title">{pick('Что требует внимания', 'What needs attention')}</h2>
          </div>
          <span className="risk-summary" data-has-high={highRisks.length > 0}>
            <i />{' '}
            {highRisks.length
              ? `${highRisks.length} ${pick('высокого уровня', 'high-level')}`
              : pick('Высоких рисков не найдено', 'No high risks found')}
          </span>
        </div>
        {groundedRisks.length ? (
          <div className="risk-preview-grid">
            {groundedRisks.slice(0, 3).map((rawRisk) => {
              const risk = localizeRisk(rawRisk, locale)
              return (
                <article key={risk.rule_id} data-severity={risk.severity}>
                  <header>
                    <AlertTriangle aria-hidden="true" />
                    <span>
                      {risk.severity === 'high'
                        ? pick('Высокий', 'High')
                        : pick('Средний', 'Medium')}
                    </span>
                  </header>
                  <h3>{risk.title}</h3>
                  <p>{risk.description}</p>
                  {risk.citation && (
                    <CitationLink citation={risk.citation} onOpen={onCitationOpen} />
                  )}
                </article>
              )
            })}
          </div>
        ) : (
          <div className="no-risk-state">
            <Check aria-hidden="true" />
            <span>
              {pick('Подтверждённые риски не сформированы.', 'No grounded risks were produced.')}
            </span>
          </div>
        )}
      </section>

      {analysis.coverage.missing_categories.length > 0 && (
        <section className="coverage-note">
          <AlertTriangle aria-hidden="true" />
          <div>
            <strong>{pick('Нужна ручная проверка', 'Manual review required')}</strong>
            <p>
              {pick('Автоматически не найдены:', 'Not found automatically:')}{' '}
              {analysis.coverage.missing_categories
                .map((category) =>
                  (locale === 'ru'
                    ? categoryMeta[category]
                    : englishCategoryMeta[category]
                  ).label.toLocaleLowerCase(locale),
                )
                .join(', ')}
              .{' '}
              {pick(
                'Это не доказывает отсутствие условий в PDF.',
                'This does not prove that the conditions are absent from the PDF.',
              )}
            </p>
          </div>
        </section>
      )}

      <p className="disclaimer">{localizedDisclaimer(locale)}</p>
    </div>
  )
}

function FlowStep({ label, value, complete }: { label: string; value: string; complete: boolean }) {
  return (
    <div className="flow-step" data-complete={complete}>
      <span className="flow-marker">
        <Check aria-hidden="true" />
      </span>
      <strong>{label}</strong>
      <small>{value}</small>
    </div>
  )
}

function EvidenceNode({
  category,
  conditions,
  onCitationOpen,
  locale,
  pick,
}: {
  category: ConditionCategory
  conditions: ExtractedConditionResponse[]
  onCitationOpen: (citation: CitationResponse) => void
  locale: 'ru' | 'en'
  pick: (ru: string, en: string) => string
}) {
  const russianMeta = categoryMeta[category]
  const meta = locale === 'ru' ? russianMeta : { ...russianMeta, ...englishCategoryMeta[category] }
  const Icon = meta.icon
  const primary = conditions[0]

  return (
    <article className={`evidence-node evidence-node-${category}`} data-missing={!primary}>
      <header>
        <span>
          <Icon aria-hidden="true" />
        </span>
        <div>
          <strong>{meta.label}</strong>
          <small>
            {conditions.length || pick('не найдено', 'not found')}{' '}
            {conditions.length ? meta.plural : ''}
          </small>
        </div>
      </header>
      <p>
        {primary?.summary ??
          pick(
            'Проверьте эту категорию вручную в исходном документе.',
            'Review this category manually in the source document.',
          )}
      </p>
      {primary ? (
        <CitationLink
          citation={primary.citation}
          onOpen={onCitationOpen}
          label={`${pick('Источник · стр.', 'Source · p.')} ${primary.citation.page_number}`}
        />
      ) : (
        <span className="manual-source">
          {pick('Без автоматической цитаты', 'No automatic citation')}
        </span>
      )}
    </article>
  )
}

function formatDate(value: string, locale: 'ru' | 'en') {
  return new Intl.DateTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(value))
}
