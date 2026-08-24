export type EvaluationModel = {
  id: 'lexical' | 'base' | 'tuned'
  nameRu: string
  nameEn: string
  noteRu: string
  noteEn: string
  hitAt1: number
  mrr: number
  hitAt3: number
}

export const evaluationModels: EvaluationModel[] = [
  {
    id: 'lexical',
    nameRu: 'Совпадение слов',
    nameEn: 'Lexical overlap',
    noteRu: 'Простой baseline без нейросети',
    noteEn: 'Simple non-neural baseline',
    hitAt1: 0.59375,
    mrr: 0.719618,
    hitAt3: 0.697917,
  },
  {
    id: 'base',
    nameRu: 'Исходный cross-encoder',
    nameEn: 'Base cross-encoder',
    noteRu: 'Multilingual MiniLM до обучения',
    noteEn: 'Multilingual MiniLM before training',
    hitAt1: 0.875,
    mrr: 0.926215,
    hitAt3: 0.96875,
  },
  {
    id: 'tuned',
    nameRu: 'TenderLens-Reranker v1',
    nameEn: 'TenderLens-Reranker v1',
    noteRu: 'После дообучения на тендерных примерах',
    noteEn: 'Fine-tuned on tender examples',
    hitAt1: 0.989583,
    mrr: 0.993056,
    hitAt3: 1,
  },
]

export const datasetSplits = [
  { id: 'train', documents: 16, queries: 384, pairs: 1536 },
  { id: 'validation', documents: 4, queries: 96, pairs: 384 },
  { id: 'test', documents: 4, queries: 96, pairs: 384 },
] as const

export const experimentMeta = {
  documents: 24,
  queries: 576,
  pairs: 2304,
  russianQueries: 384,
  englishQueries: 192,
  testMistakes: 1,
  status: 'research_candidate',
} as const

export function percentage(value: number) {
  return `${(value * 100).toFixed(1)}%`
}
