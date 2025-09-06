import { useState } from "react";
import { X, RefreshCw, AlertTriangle } from "lucide-react";
import { useKeyboardShortcut } from "../hooks/useKeyboardShortcut";

interface RecrawlDialogProps {
  isOpen: boolean;
  sourceName: string;
  sourceUrl: string;
  onConfirm: (ignoreHash: boolean) => void;
  onCancel: () => void;
  isRecrawling: boolean;
}

export function RecrawlDialog({
  isOpen,
  sourceName,
  sourceUrl,
  onConfirm,
  onCancel,
  isRecrawling,
}: RecrawlDialogProps) {
  const [ignoreHash, setIgnoreHash] = useState(false);

  // Handle Escape key to cancel
  useKeyboardShortcut('Escape', onCancel, isOpen && !isRecrawling);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-background rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-xl font-semibold">Recrawl Source</h2>
          <button
            onClick={onCancel}
            className="text-muted-foreground hover:text-foreground"
            disabled={isRecrawling}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <p className="text-sm text-muted-foreground mb-2">
              This will recrawl the source using the same settings:
            </p>
            <div className="bg-secondary/50 rounded-md p-3 space-y-1">
              <p className="text-sm">
                <span className="font-medium">Source:</span> {sourceName}
              </p>
              <p className="text-sm">
                <span className="font-medium">Base URL:</span> {sourceUrl}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={ignoreHash}
                onChange={(e) => setIgnoreHash(e.target.checked)}
                className="mt-1"
                disabled={isRecrawling}
              />
              <div>
                <p className="font-medium text-sm">
                  Force regenerate all content
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Ignore content hash and regenerate all LLM descriptions even if the page content hasn&apos;t changed.
                </p>
              </div>
            </label>

            {ignoreHash && (
              <div className="flex items-start gap-2 p-3 bg-yellow-500/10 rounded-md">
                <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5" />
                <p className="text-xs text-yellow-700 dark:text-yellow-300">
                  This will regenerate all code snippets and descriptions, which may take significantly longer and use more LLM credits.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-3 p-6 border-t border-border">
          <button
            onClick={onCancel}
            disabled={isRecrawling}
            className="flex-1 px-4 py-2 text-sm border border-input rounded-md hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(ignoreHash)}
            disabled={isRecrawling}
            className="flex-1 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isRecrawling ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" />
                Start Recrawl
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}