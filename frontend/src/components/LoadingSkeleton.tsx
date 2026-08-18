export function LoadingSkeleton() {
  return (
    <div className="loading-skeleton" aria-label="Загружаем результаты" role="status">
      <span className="sr-only">Загружаем результаты анализа</span>
      <div className="skeleton-line skeleton-title" />
      <div className="skeleton-grid">
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
      </div>
      <div className="skeleton-line" />
      <div className="skeleton-line skeleton-short" />
    </div>
  )
}
