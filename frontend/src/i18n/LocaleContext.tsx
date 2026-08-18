/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'

export type Locale = 'ru' | 'en'

type LocaleContextValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  pick: (ru: string, en: string) => string
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'ru',
  setLocale: () => undefined,
  pick: (ru) => ru,
})

export function LocaleProvider({ children }: PropsWithChildren) {
  const [locale, setLocale] = useState<Locale>(() => {
    const saved = window.localStorage.getItem('tenderlens-locale')
    return saved === 'en' ? 'en' : 'ru'
  })

  useEffect(() => {
    window.localStorage.setItem('tenderlens-locale', locale)
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      pick: (ru: string, en: string) => (locale === 'ru' ? ru : en),
    }),
    [locale],
  )

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  return useContext(LocaleContext)
}
