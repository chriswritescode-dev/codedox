import { X, Wand2, AlertCircle } from 'lucide-react'

interface FormatSourceDialogProps {
  isOpen: boolean
  sourceName: string
  totalSnippets: number
  changedSnippets: number
  preview: Array<{
    snippet_id: number
    title: string
    language: string
    original_preview: string
    formatted_preview: string
  }>
  isFormatting?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function FormatSourceDialog({
  isOpen,
  sourceName,
  totalSnippets,
  changedSnippets,
  preview,
  isFormatting = false,
  onConfirm,
  onCancel,
}: FormatSourceDialogProps) {
  if (!isOpen) return null

  const percentageChanged = totalSnippets > 0 
    ? Math.round((changedSnippets / totalSnippets) * 100) 
    : 0

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
          className="bg-background border border-border rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Wand2 className="h-5 w-5" />
              Format All Snippets
            </h2>
            <button
              onClick={onCancel}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Summary */}
          <div className="p-4 space-y-4">
            <div className="bg-secondary/50 rounded-lg p-4">
              <h3 className="font-medium mb-2">Source: {sourceName}</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total snippets:</span>
                  <span className="font-medium">{totalSnippets}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Snippets to format:</span>
                  <span className="font-medium text-primary">
                    {changedSnippets} ({percentageChanged}%)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Already well-formatted:</span>
                  <span className="font-medium text-green-600 dark:text-green-400">
                    {totalSnippets - changedSnippets}
                  </span>
                </div>
              </div>
            </div>

            {changedSnippets === 0 ? (
              <div className="flex items-center gap-2 p-4 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-lg">
                <AlertCircle className="h-5 w-5" />
                <p className="text-sm">
                  All snippets in this source are already well-formatted!
                </p>
              </div>
            ) : (
              <>
                {preview.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium text-muted-foreground">
                      Preview of changes (showing first {preview.length}):
                    </h4>
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                      {preview.map((item) => (
                        <div
                          key={item.snippet_id}
                          className="bg-secondary/30 rounded-md p-3 space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium truncate">
                              {item.title || `Snippet #${item.snippet_id}`}
                            </span>
                            <span className="px-2 py-0.5 bg-primary/10 text-primary rounded text-xs font-medium">
                              {item.language}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <p className="text-muted-foreground mb-1">Before:</p>
                              <pre className="bg-secondary/50 p-2 rounded overflow-hidden">
                                <code>{item.original_preview}</code>
                              </pre>
                            </div>
                            <div>
                              <p className="text-muted-foreground mb-1">After:</p>
                              <pre className="bg-secondary/50 p-2 rounded overflow-hidden">
                                <code>{item.formatted_preview}</code>
                              </pre>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-lg">
                  <p className="text-sm">
                    This will format {changedSnippets} snippet{changedSnippets !== 1 ? 's' : ''} in this source. 
                    The changes will be saved permanently.
                  </p>
                </div>
              </>
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
              disabled={isFormatting || changedSnippets === 0}
              className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isFormatting ? (
                <>
                  <div className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                  Formatting...
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" />
                  Format {changedSnippets} Snippet{changedSnippets !== 1 ? 's' : ''}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}