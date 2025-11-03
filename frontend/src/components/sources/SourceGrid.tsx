import { memo } from 'react'
import { Source } from '../../lib/api'
import { SourceCard } from './SourceCard'

interface SourceGridProps {
  sources: Source[]
  selectedSources: Set<string>
  onToggleSelect: (id: string) => void
  onRecrawl: (sourceId: string, options?: { ignoreHash?: boolean }) => void
  onRegenerate: (sourceId: string) => void
  onDelete: (sourceId: string) => void
  onUpdateName: (id: string, name: string) => Promise<void>
  isPendingRecrawl: boolean
  isPendingRegenerate: boolean
  isPendingDelete: boolean
}

export const SourceGrid = memo(({
  sources,
  selectedSources,
  onToggleSelect,
  onDelete,
  onRecrawl,
  onRegenerate,
  onUpdateName,
  isPendingRecrawl,
  isPendingRegenerate,
  isPendingDelete
}: SourceGridProps) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pt-2">
      {sources.map((source) => (
        <SourceCard
          key={source.id}
          source={source}
          isSelected={selectedSources.has(source.id)}
          onToggleSelect={onToggleSelect}
          onDelete={() => onDelete(source.id)}
          onRecrawl={(options) => onRecrawl(source.id, options)}
          onRegenerate={() => onRegenerate(source.id)}
          onUpdateName={onUpdateName}
          isPendingRecrawl={isPendingRecrawl}
          isPendingRegenerate={isPendingRegenerate}
          isPendingDelete={isPendingDelete}
        />
      ))}
    </div>
  )
})

SourceGrid.displayName = 'SourceGrid'