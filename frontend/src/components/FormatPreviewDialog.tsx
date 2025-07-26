import { useState } from 'react'
import { X, Wand2, Check, AlertCircle } from 'lucide-react'

interface FormatPreviewDialogProps {
  isOpen: boolean
  title: string
  original: string
  formatted: string
  language: string
  changed: boolean
  isFormatting?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function FormatPreviewDialog({
  isOpen,
  title,
  original,
  formatted,
  language,
  changed,
  isFormatting = false,
  onConfirm,
  onCancel,
}: FormatPreviewDialogProps) {
  const [viewMode, setViewMode] = useState<'side-by-side' | 'formatted'>('side-by-side')

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
        onClick={onCancel}
        aria-hidden="true"
      />
      
      {/* Dialog */}
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
        <div
          className="bg-background border border-border rounded-lg shadow-lg w-full max-w-4xl max-h-[80vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Wand2 className="h-5 w-5" />
              {title}
            </h2>
            <button
              onClick={onCancel}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Status */}
          <div className="px-4 py-3 bg-secondary/50 border-b border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Language:</span>
                <span className="px-2 py-0.5 bg-primary/10 text-primary rounded text-xs font-medium">
                  {language}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {changed ? (
                  <>
                    <Check className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-green-600 dark:text-green-400">
                      Formatting will improve code style
                    </span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      Code is already well-formatted
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* View Mode Tabs */}
          <div className="flex gap-2 px-4 pt-3">
            <button
              onClick={() => setViewMode('side-by-side')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'side-by-side'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              Side by Side
            </button>
            <button
              onClick={() => setViewMode('formatted')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'formatted'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              Formatted Only
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-hidden p-4">
            {viewMode === 'side-by-side' ? (
              <div className="grid grid-cols-2 gap-4 h-full">
                <div className="flex flex-col h-full">
                  <h3 className="text-sm font-medium mb-2 text-muted-foreground">
                    Original
                  </h3>
                  <div className="flex-1 bg-secondary/50 rounded-md overflow-auto">
                    <pre className="p-3 text-sm">
                      <code className={`language-${language}`}>{original}</code>
                    </pre>
                  </div>
                </div>
                <div className="flex flex-col h-full">
                  <h3 className="text-sm font-medium mb-2 text-muted-foreground">
                    Formatted
                  </h3>
                  <div className="flex-1 bg-secondary/50 rounded-md overflow-auto">
                    <pre className="p-3 text-sm">
                      <code className={`language-${language}`}>{formatted}</code>
                    </pre>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col">
                <h3 className="text-sm font-medium mb-2 text-muted-foreground">
                  Formatted Code
                </h3>
                <div className="flex-1 bg-secondary/50 rounded-md overflow-auto">
                  <pre className="p-3 text-sm">
                    <code className={`language-${language}`}>{formatted}</code>
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-4 border-t border-border">
            <button
              onClick={onCancel}
              disabled={isFormatting}
              className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isFormatting || !changed}
              className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isFormatting ? (
                <>
                  <div className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  Applying...
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  Apply Formatting
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}