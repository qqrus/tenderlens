import type { RiskCheckResponse } from '../api/types'
import { useLocale } from '../i18n/LocaleContext'

export function RiskBadge({ severity }: Pick<RiskCheckResponse, 'severity'>) {
  const { pick } = useLocale()
  return (
    <span className="risk-badge" data-severity={severity}>
      {severity === 'high'
        ? pick('Высокий риск', 'High risk')
        : pick('Средний риск', 'Medium risk')}
    </span>
  )
}
