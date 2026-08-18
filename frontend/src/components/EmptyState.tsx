import { FileSearch2 } from 'lucide-react'

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="inline-empty-state">
      <FileSearch2 aria-hidden="true" />
      <p>{message}</p>
    </div>
  )
}
