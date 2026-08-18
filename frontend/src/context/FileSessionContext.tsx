/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'

type FileSession = {
  file: File | null
  objectUrl: string | null
  setFile: (file: File) => void
  clearFile: () => void
}

const FileSessionContext = createContext<FileSession | null>(null)

export function FileSessionProvider({ children }: PropsWithChildren) {
  const [file, setFileState] = useState<File | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  const setFile = useCallback((nextFile: File) => {
    setFileState(nextFile)
    setObjectUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous)
      return URL.createObjectURL(nextFile)
    })
  }, [])

  const clearFile = useCallback(() => {
    setFileState(null)
    setObjectUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous)
      return null
    })
  }, [])

  useEffect(
    () => () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    },
    [objectUrl],
  )

  const value = useMemo(
    () => ({ file, objectUrl, setFile, clearFile }),
    [clearFile, file, objectUrl, setFile],
  )

  return <FileSessionContext.Provider value={value}>{children}</FileSessionContext.Provider>
}

export function useFileSession() {
  const context = useContext(FileSessionContext)
  if (!context) throw new Error('useFileSession must be used inside FileSessionProvider')
  return context
}
