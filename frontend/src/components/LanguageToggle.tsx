import { Languages } from 'lucide-react'
import { useLocale } from '../i18n/LocaleContext'

export function LanguageToggle() {
  const { locale, setLocale, pick } = useLocale()

  return (
    <div className="language-toggle" aria-label={pick('Язык интерфейса', 'Interface language')}>
      <Languages aria-hidden="true" />
      <button type="button" data-active={locale === 'ru'} onClick={() => setLocale('ru')}>
        RU
      </button>
      <button type="button" data-active={locale === 'en'} onClick={() => setLocale('en')}>
        EN
      </button>
    </div>
  )
}
