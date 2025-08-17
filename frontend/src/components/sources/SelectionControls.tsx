import React from 'react'
import { Check } from 'lucide-react'

interface SelectionControlsProps {
  selectedCount: number
  totalCount: number
  onSelectAll: () => void
  onDeselectAll: () => void
  onBulkDelete: () => void
}

export const SelectionControls: React.FC<SelectionControlsProps> = ({
  selectedCount,
  totalCount,
  onSelectAll,
  onDeselectAll,
  onBulkDelete
}) => {
  const allSelected = selectedCount === totalCount && totalCount > 0
  const someSelected = selectedCount > 0 && selectedCount < totalCount

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-secondary/50 rounded-md">
      <div className="flex items-center gap-2">
        <div
          onClick={() => {
            if (allSelected) {
              onDeselectAll()
            } else {
              onSelectAll()
            }
          }}
          className="cursor-pointer"
          title="Select all matching sources"
        >
          <div
            className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
              allSelected
                ? "bg-primary border-primary"
                : someSelected
                  ? "bg-primary/50 border-primary"
                  : "border-input bg-background hover:border-primary"
            }`}
          >
            {allSelected && (
              <Check className="h-3 w-3 text-primary-foreground" />
            )}
            {someSelected && (
              <div className="w-2 h-2 bg-primary-foreground rounded-sm" />
            )}
          </div>
        </div>
        <span className="text-sm font-medium whitespace-nowrap">
          {selectedCount}/{totalCount}
        </span>
      </div>

      {selectedCount > 0 && (
        <button
          onClick={onDeselectAll}
          className="text-sm text-muted-foreground hover:text-foreground whitespace-nowrap"
        >
          Clear
        </button>
      )}

      <button
        onClick={onBulkDelete}
        disabled={selectedCount === 0}
        className={`px-3 py-1 text-sm rounded-md transition-colors whitespace-nowrap ${
          selectedCount > 0
            ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
            : "bg-secondary text-muted-foreground cursor-not-allowed"
        }`}
        title="Delete selected sources"
      >
        Delete ({selectedCount})
      </button>
    </div>
  )
}