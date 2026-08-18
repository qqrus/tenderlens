const MAX_FILE_SIZE = 20 * 1024 * 1024

export function validatePdf(file: File): string | null {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    return 'Поддерживаются только PDF-файлы.'
  }
  if (file.size > MAX_FILE_SIZE) return 'Размер файла не должен превышать 20 МБ.'
  if (file.size === 0) return 'Файл пуст. Выберите другой PDF.'
  return null
}
