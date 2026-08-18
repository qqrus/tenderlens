import { AlertTriangle, RotateCcw } from 'lucide-react'
import { useLocale } from '../i18n/LocaleContext'

type Props = {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorState({ title, message, onRetry }: Props) {
  const { pick } = useLocale()
  return (
    <section className="error-state" role="alert">
      <span className="error-icon">
        <AlertTriangle aria-hidden="true" />
      </span>
      <div>
        <h2>{title ?? pick('Не удалось загрузить данные', 'Could not load data')}</h2>
        <p>{message}</p>
        {onRetry && (
          <button className="secondary-button" type="button" onClick={onRetry}>
            <RotateCcw aria-hidden="true" /> {pick('Повторить', 'Retry')}
          </button>
        )}
      </div>
    </section>
  )
}
