import type { ConditionCategory, RiskCheckResponse } from '../api/types'
import type { Locale } from './LocaleContext'

type RiskCopy = Pick<RiskCheckResponse, 'title' | 'description' | 'recommendation'>

const riskCopy: Record<string, Record<Locale, RiskCopy>> = {
  deadline_compliance: {
    ru: {
      title: 'Соблюдение сроков',
      description: 'В документе найден срок подачи или исполнения.',
      recommendation:
        'Уточните часовой пояс, канал подачи и установите внутренний срок раньше официального.',
    },
    en: {
      title: 'Deadline compliance',
      description: 'The document contains a submission or delivery deadline.',
      recommendation: 'Confirm the timezone, submission channel and an earlier internal cutoff.',
    },
  },
  budget_fit: {
    ru: {
      title: 'Соответствие бюджету',
      description: 'В документе найдено условие о бюджете или цене контракта.',
      recommendation:
        'Проверьте налоги, валюту, включённые расходы и коммерческую целесообразность.',
    },
    en: {
      title: 'Budget fit',
      description: 'The document contains a budget or contract value condition.',
      recommendation: 'Validate taxes, currency, included costs and commercial feasibility.',
    },
  },
  penalty_exposure: {
    ru: {
      title: 'Риск штрафов',
      description: 'В документе найдено условие о штрафе, пени или неустойке.',
      recommendation:
        'Рассчитайте максимальную ответственность и вручную проверьте события, которые запускают санкции.',
    },
    en: {
      title: 'Penalty exposure',
      description: 'The document contains a penalty, fine or liquidated damages condition.',
      recommendation: 'Quantify the maximum exposure and review triggering events manually.',
    },
  },
  eligibility_evidence: {
    ru: {
      title: 'Подтверждение соответствия',
      description: 'В документе найдены требования к участнику или поставщику.',
      recommendation:
        'Назначьте ответственного и подтверждающий документ для каждого требования до подачи заявки.',
    },
    en: {
      title: 'Eligibility evidence',
      description: 'The document contains bidder or supplier requirements.',
      recommendation:
        'Map every requirement to an owner and supporting document before submission.',
    },
  },
}

const categoryNames: Record<ConditionCategory, Record<Locale, string>> = {
  deadline: { ru: 'срок', en: 'deadline' },
  budget: { ru: 'бюджет', en: 'budget' },
  penalty: { ru: 'штрафы', en: 'penalty' },
  requirement: { ru: 'требования', en: 'requirements' },
}

export function localizeRisk(risk: RiskCheckResponse, locale: Locale): RiskCheckResponse {
  const known = riskCopy[risk.rule_id]?.[locale]
  if (known) return { ...risk, ...known }
  if (risk.rule_id.startsWith('missing_')) {
    const category = risk.rule_id.slice('missing_'.length) as ConditionCategory
    const name = categoryNames[category]?.[locale] ?? category
    return {
      ...risk,
      title: locale === 'ru' ? `Не найдено: ${name}` : `${name} not found`,
      description:
        locale === 'ru'
          ? `Автоматический анализ не нашёл явное условие категории «${name}».`
          : `Automatic analysis did not find an explicit ${name} condition.`,
      recommendation:
        locale === 'ru'
          ? 'Проверьте исходный PDF вручную до принятия решения.'
          : 'Review the original PDF manually before making a decision.',
    }
  }
  return risk
}

export function localizedDisclaimer(locale: Locale) {
  return locale === 'ru'
    ? 'TenderLens анализирует документ и не является юридической консультацией.'
    : 'TenderLens provides document analysis, not legal advice.'
}
