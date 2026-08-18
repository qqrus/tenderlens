import { Check, FileSearch, LoaderCircle, Upload } from 'lucide-react'
import type { DocumentStatusValue } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'

type Props = {
  status: DocumentStatusValue
}

export function DocumentStatus({ status }: Props) {
  const { pick } = useLocale()
  const stages = [
    { key: 'uploaded', label: pick('Загрузка', 'Upload'), icon: Upload },
    { key: 'processing', label: pick('Извлечение текста', 'Text extraction'), icon: FileSearch },
    { key: 'ready', label: pick('Готово', 'Ready'), icon: Check },
  ] as const
  const currentIndex = status === 'ready' ? 2 : status === 'processing' ? 1 : 0

  return (
    <section
      className="status-panel"
      aria-live="polite"
      aria-label={pick('Статус документа', 'Document status')}
    >
      <div className="status-heading">
        <div>
          <span className="eyebrow">{pick('Обработка документа', 'Document processing')}</span>
          <h2>
            {status === 'ready'
              ? pick('Документ готов', 'Document ready')
              : pick('Проверяем содержимое PDF', 'Checking PDF content')}
          </h2>
        </div>
        {status !== 'ready' && <LoaderCircle className="spin status-spinner" aria-hidden="true" />}
      </div>
      <ol className="status-stages">
        {stages.map(({ key, label, icon: Icon }, index) => (
          <li
            key={key}
            data-state={
              index < currentIndex ? 'complete' : index === currentIndex ? 'active' : 'pending'
            }
          >
            <span className="stage-marker">
              <Icon aria-hidden="true" />
            </span>
            <span>{label}</span>
          </li>
        ))}
      </ol>
      {status !== 'ready' && (
        <p>
          {pick(
            'Статус обновляется автоматически. Точный процент backend не предоставляет.',
            'Status updates automatically. The backend does not provide an exact percentage.',
          )}
        </p>
      )}
    </section>
  )
}
