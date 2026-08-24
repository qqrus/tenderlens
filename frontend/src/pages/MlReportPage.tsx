import { ArrowLeft, ArrowUpRight, Database, FlaskConical, ShieldAlert } from 'lucide-react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { LanguageToggle } from '../components/LanguageToggle'
import { datasetSplits, evaluationModels, experimentMeta, percentage } from '../data/mlReport'
import { useLocale } from '../i18n/LocaleContext'

export function MlReportPage() {
  const { locale, pick } = useLocale()
  const tuned = evaluationModels[2]!
  const base = evaluationModels[1]!
  const improvement = (tuned.hitAt1 - base.hitAt1) * 100

  return (
    <main className="ml-report-shell">
      <header className="ml-report-topbar">
        <Link className="product-brand" to="/" aria-label="TenderLens — документы">
          <span className="product-wordmark">
            Tender<span>Lens</span>
          </span>
          <span className="brand-brackets" aria-hidden="true" />
        </Link>
        <div>
          <Link className="secondary-button" to="/">
            <ArrowLeft aria-hidden="true" /> {pick('К документам', 'Back to documents')}
          </Link>
          <LanguageToggle />
        </div>
      </header>

      <div className="ml-report-content">
        <section className="ml-report-hero">
          <div>
            <span className="page-kicker">
              {pick('ML-лаборатория · эксперимент v1', 'ML lab · experiment v1')}
            </span>
            <h1>{pick('Как улучшался поиск ответа', 'How answer retrieval improved')}</h1>
            <p>
              {pick(
                'Показываем путь от простого поиска по словам до дообученного reranker. Все цифры воспроизводятся из evaluation-файлов проекта.',
                'From lexical matching to a fine-tuned reranker. Every number is reproducible from the project evaluation files.',
              )}
            </p>
          </div>
          <div className="research-status">
            <FlaskConical aria-hidden="true" />
            <span>{pick('Статус модели', 'Model status')}</span>
            <strong>research candidate</strong>
            <small>{pick('ещё не production', 'not production yet')}</small>
          </div>
        </section>

        <section
          className="ml-highlight-grid"
          aria-label={pick('Ключевые результаты', 'Key results')}
        >
          <MetricCard
            label="Test Hit@1"
            value={percentage(tuned.hitAt1)}
            note={pick('правильный фрагмент первым', 'correct passage ranked first')}
          />
          <MetricCard
            label={pick('Прирост Hit@1', 'Hit@1 uplift')}
            value={`+${improvement.toFixed(1)} п.п.`}
            note={pick('относительно исходной модели', 'versus the base model')}
            accent
          />
          <MetricCard
            label={pick('Ошибок на test', 'Test errors')}
            value={`${experimentMeta.testMistakes} / 96`}
            note={pick('на синтетическом holdout', 'on synthetic holdout')}
          />
          <MetricCard
            label={pick('Стоимость API', 'API cost')}
            value="$0"
            note={pick('локальное CPU-обучение', 'local CPU training')}
          />
        </section>

        <section className="ml-panel" aria-labelledby="quality-chart-title">
          <div className="ml-panel-heading">
            <div>
              <span className="page-kicker">{pick('Сравнение моделей', 'Model comparison')}</span>
              <h2 id="quality-chart-title">
                {pick('Качество на test-наборе', 'Quality on the test split')}
              </h2>
            </div>
            <div className="metric-legend" aria-label={pick('Легенда', 'Legend')}>
              <span data-metric="hit1">Hit@1</span>
              <span data-metric="mrr">MRR</span>
              <span data-metric="hit3">Hit@3</span>
            </div>
          </div>
          <div
            className="model-chart"
            role="img"
            aria-label={pick(
              'Групповой график Hit@1, MRR и Hit@3 для трёх методов поиска',
              'Grouped chart of Hit@1, MRR and Hit@3 for three retrieval methods',
            )}
          >
            {evaluationModels.map((model) => (
              <div className="model-chart-row" key={model.id} data-model={model.id}>
                <div className="model-chart-label">
                  <strong>{locale === 'ru' ? model.nameRu : model.nameEn}</strong>
                  <small>{locale === 'ru' ? model.noteRu : model.noteEn}</small>
                </div>
                <div className="model-bars">
                  <MetricBar metric="hit1" value={model.hitAt1} />
                  <MetricBar metric="mrr" value={model.mrr} />
                  <MetricBar metric="hit3" value={model.hitAt3} />
                </div>
              </div>
            ))}
          </div>
          <p className="chart-footnote">
            {pick(
              'Чем ближе к 100%, тем выше правильный фрагмент в выдаче. Test содержит 96 вопросов из документов, не использованных для обновления весов.',
              'Closer to 100% means the correct passage ranks higher. Test contains 96 questions from documents not used to update model weights.',
            )}
          </p>
        </section>

        <div className="ml-report-grid">
          <section className="ml-panel dataset-panel" aria-labelledby="dataset-title">
            <div className="ml-panel-heading">
              <div>
                <span className="page-kicker">{pick('Данные', 'Dataset')}</span>
                <h2 id="dataset-title">
                  {pick('Как разделён датасет', 'How the dataset is split')}
                </h2>
              </div>
              <Database aria-hidden="true" />
            </div>
            <div
              className="split-bar"
              role="img"
              aria-label={pick(
                'Train 67%, validation 17%, test 17%',
                'Train 67%, validation 17%, test 17%',
              )}
            >
              {datasetSplits.map((split) => (
                <span
                  key={split.id}
                  data-split={split.id}
                  style={
                    {
                      '--split': `${(split.queries / experimentMeta.queries) * 100}%`,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
            <div className="split-list">
              {datasetSplits.map((split) => (
                <div key={split.id}>
                  <span data-split={split.id} />
                  <strong>{split.id}</strong>
                  <small>
                    {split.documents} {pick('док.', 'docs')} · {split.queries}{' '}
                    {pick('вопросов', 'queries')} · {split.pairs} {pick('пар', 'pairs')}
                  </small>
                </div>
              ))}
            </div>
          </section>

          <section className="ml-panel limitations-panel" aria-labelledby="limitations-title">
            <div className="ml-panel-heading">
              <div>
                <span className="page-kicker">
                  {pick('Честные ограничения', 'Honest limitations')}
                </span>
                <h2 id="limitations-title">
                  {pick('Что эти цифры пока не доказывают', 'What these numbers do not prove yet')}
                </h2>
              </div>
              <ShieldAlert aria-hidden="true" />
            </div>
            <ul>
              <li>
                {pick(
                  'Train, validation и test созданы одним генератором.',
                  'Train, validation and test share one generator.',
                )}
              </li>
              <li>
                {pick(
                  'Модель ещё не проверена на независимо размеченном наборе реальных тендеров.',
                  'The model has not yet passed an independently labelled real-tender holdout.',
                )}
              </li>
              <li>
                {pick(
                  'Один test-вопрос перепутал срок исполнения с гарантийным сроком.',
                  'One test query confused a delivery term with a warranty period.',
                )}
              </li>
            </ul>
            <div className="next-gate">
              <span>{pick('Следующий контрольный этап', 'Next quality gate')}</span>
              <strong>{pick('Real-document holdout + OCR', 'Real-document holdout + OCR')}</strong>
            </div>
          </section>
        </div>

        <footer className="ml-report-footer">
          <span>
            {pick(
              'Источник данных: evals/reranker_experiment_v1.json',
              'Data source: evals/reranker_experiment_v1.json',
            )}
          </span>
          <a
            href="https://github.com/qqrus/tenderlens/tree/main/evals"
            target="_blank"
            rel="noreferrer"
          >
            {pick('Открыть артефакты эксперимента', 'Open experiment artifacts')}{' '}
            <ArrowUpRight aria-hidden="true" />
          </a>
        </footer>
      </div>
    </main>
  )
}

function MetricCard({
  label,
  value,
  note,
  accent = false,
}: {
  label: string
  value: string
  note: string
  accent?: boolean
}) {
  return (
    <article className="ml-metric-card" data-accent={accent}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function MetricBar({ metric, value }: { metric: 'hit1' | 'mrr' | 'hit3'; value: number }) {
  return (
    <div className="metric-bar" data-metric={metric} aria-label={`${metric}: ${percentage(value)}`}>
      <span style={{ '--value': `${value * 100}%` } as CSSProperties} />
      <strong>{percentage(value)}</strong>
    </div>
  )
}
