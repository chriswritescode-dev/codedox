import React, { memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Code, Check } from 'lucide-react'
import { EditableSourceName } from '../EditableSourceName'
import { SourceActionsMenu } from '../SourceActionsMenu'
import { Source } from '../../lib/api'
import { cn } from '../../lib/utils'

interface SourceCardProps {
  source: Source
  isSelected: boolean
  onToggleSelect: (id: string) => void
  onRecrawl: (options?: { ignoreHash?: boolean }) => void
  onRegenerate: () => void
  onDelete: () => void
  onUpdateName: (id: string, name: string) => Promise<void>
  isPendingRecrawl: boolean
  isPendingRegenerate: boolean
  isPendingDelete: boolean
}

export const SourceCard = memo(({
  source,
  isSelected,
  onToggleSelect,
  onRecrawl,
  onRegenerate,
  onDelete,
  onUpdateName,
  isPendingRecrawl,
  isPendingRegenerate,
  isPendingDelete
}: SourceCardProps) => {
  const navigate = useNavigate()

  const handleCardClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    const isInteractive = target.closest('button, input, a, [role="button"]')
    if (!isInteractive) {
      navigate(`/sources/${source.id}`)
    }
  }

  return (
    <div
      className={cn(
        "ring-2 relative bg-secondary/50 rounded-lg p-6 hover:bg-secondary transition-colors group cursor-pointer mx-1",
        isSelected ? "ring-primary" : "ring-transparent"
      )}
      onClick={handleCardClick}
    >
      <div
        className="absolute top-4 left-4 z-10"
        onClick={(e) => {
          e.stopPropagation();
          onToggleSelect(source.id);
        }}
      >
        <div
          className={`w-6 h-6 rounded border-2 flex items-center justify-center cursor-pointer ${
            isSelected
              ? "bg-primary border-primary"
              : "border-input bg-background hover:border-primary"
          }`}
        >
          {isSelected && <Check className="h-4 w-4 text-primary-foreground" />}
        </div>
      </div>

      <div className="flex items-start justify-end mb-4">
        <SourceActionsMenu
          source={source}
          onRecrawl={onRecrawl}
          onRegenerate={onRegenerate}
          onDelete={onDelete}
          isRecrawling={isPendingRecrawl}
          isRegenerating={isPendingRegenerate}
          isDeleting={isPendingDelete}
          variant="dropdown"
          size="sm"
        />
      </div>

      <div className="mb-4">
        <div
          onClick={(e) => e.stopPropagation()}
          className="inline-block w-fit"
        >
          <EditableSourceName
            id={source.id}
            name={source.name}
            version={source.version || undefined}
            onUpdate={onUpdateName}
            className="text-lg font-medium"
          />
        </div>
        <div className="text-xs text-muted-foreground mt-1 truncate">
          {source.base_url}
        </div>
      </div>

      <div className="flex items-center justify-between flex-wrap">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center text-muted-foreground">
            <FileText className="h-4 w-4 mr-1" />
            {source.documents_count} docs
          </div>
          <div className="flex items-center text-muted-foreground">
            <Code className="h-4 w-4 mr-1" />
            {source.snippets_count} snippets
          </div>
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(source.created_at).toLocaleDateString()}
        </span>
      </div>
    </div>
  );
})

SourceCard.displayName = 'SourceCard'
