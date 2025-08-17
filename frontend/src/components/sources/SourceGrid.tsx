import React, { memo } from 'react'
import { Source } from '../../lib/api'
import { SourceCard } from './SourceCard'

interface SourceGridProps {
  sources: Source[]
  selectedSources: Set<string>
  onToggleSelect: (id: string) => void
  onDelete: (e: React.MouseEvent, source: { id: string; name: string }) => void
  onRecrawl: (e: React.MouseEvent, source: { id: string; name: string; base_url: string }) => void
  onUpdateName: (id: string, name: string) => Promise<void>
  isPendingRecrawl: boolean
}

export const SourceGrid = memo(({
  sources,
  selectedSources,
  onToggleSelect,
  onDelete,
  onRecrawl,
  onUpdateName,
  isPendingRecrawl
}: SourceGridProps) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pt-2">
      {sources.map((source) => (
        <SourceCard
          key={source.id}
          source={source}
          isSelected={selectedSources.has(source.id)}
          onToggleSelect={onToggleSelect}
          onDelete={onDelete}
          onRecrawl={onRecrawl}
          onUpdateName={onUpdateName}
          isPendingRecrawl={isPendingRecrawl}
        />
      ))}
    </div>
  )
})

SourceGrid.displayName = 'SourceGrid'