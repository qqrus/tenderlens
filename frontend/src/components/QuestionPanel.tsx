import {
  AlertCircle,
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  FileText,
  LoaderCircle,
  SearchCheck,
} from 'lucide-react'
import { useState } from 'react'
import { askQuestion, humanizeError } from '../api/client'
import type { AnswerResponse, CitationResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'
import { CitationLink } from './CitationLink'

type Props = {
  documentId: string
  onCitationOpen: (citation: CitationResponse) => void
}

type Exchange = {
  question: string
  answer: AnswerResponse
}

export function QuestionPanel({ documentId, onCitationOpen }: Props) {
  const { locale, pick } = useLocale()
  const suggestions =
    locale === 'ru'
      ? [
          'Какой крайний срок подачи заявки?',
          'Какие штрафы предусмотрены договором?',
          'Какой размер обеспечения заявки?',
        ]
      : [
          'What is the submission deadline?',
          'What penalties does the contract contain?',
          'What is the bid security amount?',
        ]
  const [question, setQuestion] = useState('')
  const [exchange, setExchange] = useState<Exchange | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    const normalized = question.trim()
    if (normalized.length < 2 || isSubmitting) return
    setIsSubmitting(true)
    setError(null)
    try {
      const answer = await askQuestion(documentId, normalized)
      setExchange({ question: normalized, answer })
      setQuestion('')
    } catch (requestError) {
      setError(humanizeError(requestError, locale))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="question-panel">
      <header className="question-page-header">
        <div>
          <span className="page-kicker">
            {pick('Точный поиск по документу', 'Precise document search')}
          </span>
          <h1>{pick('Ответ с доказательствами', 'Evidence-backed answer')}</h1>
          <p>
            {pick(
              'Ответ формируется только из найденных фрагментов и остаётся связанным с исходным PDF.',
              'The answer is built only from retrieved fragments and remains linked to the source PDF.',
            )}
          </p>
        </div>
        <span className="search-mode">
          <SearchCheck aria-hidden="true" /> {pick('Проверяемый режим', 'Verifiable mode')}
        </span>
      </header>

      {exchange ? (
        <article className="answer-workbench">
          <div className="answer-query">
            <span>{pick('Ваш вопрос', 'Your question')}</span>
            <strong>{exchange.question}</strong>
          </div>
          <div className="answer-result">
            <header data-grounded={exchange.answer.grounded}>
              {exchange.answer.grounded ? (
                <CheckCircle2 aria-hidden="true" />
              ) : (
                <AlertCircle aria-hidden="true" />
              )}
              <span>
                {exchange.answer.grounded
                  ? pick('Подтверждено источниками', 'Verified by sources')
                  : pick('Недостаточно подтверждений', 'Insufficient evidence')}
              </span>
            </header>
            <p>{exchange.answer.answer}</p>
          </div>

          {exchange.answer.citations.length > 0 && (
            <section className="evidence-chain" aria-labelledby="evidence-chain-title">
              <div className="section-heading compact">
                <div>
                  <span className="page-kicker">{pick('Трассировка ответа', 'Answer trace')}</span>
                  <h2 id="evidence-chain-title">
                    {pick('Цепочка доказательств', 'Evidence chain')}
                  </h2>
                </div>
                <span className="technical-note">
                  {exchange.answer.citations.length} {pick('источника', 'sources')}
                </span>
              </div>
              <div className="chain-table" role="list">
                {exchange.answer.citations.map((citation, index) => (
                  <div className="chain-row" role="listitem" key={citation.chunk_id}>
                    <span className="chain-index">[{index + 1}]</span>
                    <div className="chain-claim">
                      <small>{pick('Фрагмент ответа', 'Answer fragment')}</small>
                      <p>«{citation.quote}»</p>
                    </div>
                    <ArrowRight className="chain-arrow" aria-hidden="true" />
                    <div className="chain-source">
                      <FileText aria-hidden="true" />
                      <span>
                        <small>{pick('Исходный PDF', 'Source PDF')}</small>
                        <strong>
                          {pick('Страница', 'Page')} {citation.page_number}
                        </strong>
                      </span>
                    </div>
                    <CitationLink
                      citation={citation}
                      onOpen={onCitationOpen}
                      label={pick('Проверить', 'Verify')}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {!exchange.answer.grounded && (
            <p className="manual-note">
              {pick(
                'Не используйте этот ответ как установленный факт без ручной проверки PDF.',
                'Do not treat this answer as established fact without manually checking the PDF.',
              )}
            </p>
          )}
        </article>
      ) : (
        <div className="question-empty-visual" aria-hidden="true">
          <div className="question-orbit">
            <i />
            <i />
            <i />
            <span>
              <SearchCheck />
            </span>
          </div>
          <p>
            {pick(
              'Задайте вопрос — TenderLens покажет ответ и путь до первоисточника.',
              'Ask a question — TenderLens will show the answer and its source trail.',
            )}
          </p>
        </div>
      )}

      <form
        className="question-composer"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <label htmlFor="question">
          {pick('Вопрос по документу', 'Question about the document')}
        </label>
        <div className="question-input-wrap">
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={2000}
            placeholder={pick(
              'Например: какой размер обеспечения заявки?',
              'For example: what is the bid security amount?',
            )}
            rows={3}
          />
          <button
            className="question-submit"
            type="submit"
            disabled={question.trim().length < 2 || isSubmitting}
            aria-label={pick('Отправить вопрос', 'Submit question')}
          >
            {isSubmitting ? (
              <LoaderCircle className="spin" aria-hidden="true" />
            ) : (
              <ArrowUp aria-hidden="true" />
            )}
          </button>
        </div>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <div
          className="question-suggestions"
          aria-label={pick('Примеры вопросов', 'Example questions')}
        >
          {suggestions.map((suggestion) => (
            <button key={suggestion} type="button" onClick={() => setQuestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      </form>
    </section>
  )
}
