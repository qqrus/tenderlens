import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocaleProvider, useLocale } from '../i18n/LocaleContext'
import { LanguageToggle } from './LanguageToggle'

function Probe() {
  const { pick } = useLocale()
  return <span>{pick('Русский интерфейс', 'English interface')}</span>
}

describe('LanguageToggle', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
      },
    })
  })

  it('uses Russian by default and switches to English', async () => {
    render(
      <LocaleProvider>
        <LanguageToggle />
        <Probe />
      </LocaleProvider>,
    )

    expect(screen.getByText('Русский интерфейс')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByText('English interface')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })
})
