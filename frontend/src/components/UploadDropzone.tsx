import { FileCheck2, FileUp, LoaderCircle, UploadCloud, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useLocale } from '../i18n/LocaleContext'
import { validatePdf } from './uploadValidation'

type Props = {
  selectedFile: File | null
  isUploading: boolean
  onFileChange: (file: File | null) => void
  onUpload: () => void
}

export function UploadDropzone({ selectedFile, isUploading, onFileChange, onUpload }: Props) {
  const { locale, pick } = useLocale()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const chooseFile = (file: File | undefined) => {
    if (!file) return
    const error = validatePdf(file)
    setValidationError(error)
    onFileChange(error ? null : file)
  }

  return (
    <section className="upload-card" aria-labelledby="upload-heading">
      <div
        className="dropzone"
        data-dragging={isDragging}
        data-selected={Boolean(selectedFile)}
        onDragEnter={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget.contains(event.relatedTarget as Node)) return
          setIsDragging(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          chooseFile(event.dataTransfer.files[0])
        }}
      >
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => chooseFile(event.target.files?.[0])}
          aria-label={pick('Выбрать PDF-файл', 'Choose PDF file')}
        />

        {selectedFile ? (
          <div className="selected-file">
            <span className="file-icon">
              <FileCheck2 aria-hidden="true" />
            </span>
            <div>
              <strong>{selectedFile.name}</strong>
              <span>
                {formatBytes(selectedFile.size, locale)} ·{' '}
                {pick('PDF готов к загрузке', 'PDF ready to upload')}
              </span>
            </div>
            <button
              className="icon-button"
              type="button"
              onClick={() => {
                onFileChange(null)
                setValidationError(null)
                if (inputRef.current) inputRef.current.value = ''
              }}
              aria-label={pick('Удалить выбранный файл', 'Remove selected file')}
              disabled={isUploading}
            >
              <X aria-hidden="true" />
            </button>
          </div>
        ) : (
          <button
            className="dropzone-prompt"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            <span className="upload-icon">
              <UploadCloud aria-hidden="true" />
            </span>
            <span>
              <strong id="upload-heading">
                {pick('Перетащите тендерный PDF', 'Drop a tender PDF here')}
              </strong>
              <small>
                {pick(
                  'или нажмите, чтобы выбрать файл · до 20 МБ',
                  'or click to choose a file · up to 20 MB',
                )}
              </small>
            </span>
          </button>
        )}
      </div>

      {validationError && (
        <p className="field-error" role="alert">
          {locale === 'ru' ? validationError : translateValidationError(validationError)}
        </p>
      )}

      <button
        className="primary-button upload-submit"
        type="button"
        onClick={onUpload}
        disabled={!selectedFile || isUploading}
      >
        {isUploading ? (
          <>
            <LoaderCircle className="spin" aria-hidden="true" />{' '}
            {pick('Загружаем документ', 'Uploading document')}
          </>
        ) : (
          <>
            <FileUp aria-hidden="true" /> {pick('Начать анализ', 'Start analysis')}
          </>
        )}
      </button>
    </section>
  )
}

function formatBytes(bytes: number, locale: 'ru' | 'en') {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} ${locale === 'ru' ? 'КБ' : 'KB'}`
  return `${(bytes / 1024 / 1024).toFixed(1)} ${locale === 'ru' ? 'МБ' : 'MB'}`
}

function translateValidationError(message: string) {
  if (message.includes('только PDF')) return 'Only PDF files are supported.'
  if (message.includes('20 МБ')) return 'The file must not exceed 20 MB.'
  if (message.includes('пуст')) return 'The file is empty. Choose another PDF.'
  return message
}
