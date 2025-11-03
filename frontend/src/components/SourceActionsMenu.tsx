import { useState } from "react";
import { MoreHorizontal, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { ActionDialog } from "./ActionDialog";

interface SourceActionsMenuProps {
  source: {
    id: string;
    name: string;
    base_url?: string;
    documents_count: number;
    snippets_count: number;
    source_type: string;
  };
  onRecrawl: (options?: { ignoreHash?: boolean }) => void;
  onRegenerate: () => void;
  onDelete: () => void;
  isRecrawling?: boolean;
  isRegenerating?: boolean;
  isDeleting?: boolean;
  showDelete?: boolean;
  variant?: "dropdown" | "buttons";
  size?: "sm" | "md" | "lg";
}

export function SourceActionsMenu({
  source,
  onRecrawl,
  onRegenerate,
  onDelete,
  isRecrawling = false,
  isRegenerating = false,
  isDeleting = false,
  showDelete = true,
  variant = "dropdown",
  size = "sm",
}: SourceActionsMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [actionType, setActionType] = useState<'recrawl' | 'regenerate' | 'delete' | null>(null);

  const handleAction = (type: 'recrawl' | 'regenerate' | 'delete') => {
    setActionType(type);
    setIsOpen(false);
  };

  const handleConfirm = (options?: { ignoreHash?: boolean }) => {
    switch (actionType) {
      case 'recrawl':
        onRecrawl(options);
        setActionType(null);
        break;
      case 'regenerate':
        onRegenerate();
        // Don't close for regenerate - ActionDialog with progress tracking will handle it
        break;
      case 'delete':
        onDelete();
        setActionType(null);
        break;
    }
  };

  const handleCancel = () => {
    setActionType(null);
  };

  const isAnyActionInProgress = isRecrawling || isRegenerating || isDeleting;

  const actionDialogs = (
    <>
      <ActionDialog
        isOpen={actionType === 'regenerate'}
        type="regenerate"
        sourceName={source.name}
        sourceId={source.id}
        itemCount={source.snippets_count}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        isConfirming={isRegenerating}
        enableProgressTracking
      />

      <ActionDialog
        isOpen={actionType === 'recrawl'}
        type="recrawl"
        sourceName={source.name}
        sourceUrl={source.base_url || ''}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        isConfirming={isRecrawling}
        showForceRegenerateOption
      />

      {showDelete && (
        <ActionDialog
          isOpen={actionType === 'delete'}
          type="delete"
          sourceName={source.name}
          itemCount={source.documents_count}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
          isConfirming={isDeleting}
        />
      )}
    </>
  );

  if (variant === "buttons") {
    return (
      <>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleAction('regenerate')}
            disabled={isAnyActionInProgress}
            className={`flex items-center px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-primary/10 disabled:opacity-50 disabled:cursor-not-allowed ${
              size === "sm" ? "px-2 py-1 text-xs" : size === "lg" ? "px-4 py-2" : ""
            }`}
          >
            <Sparkles className={`h-4 w-4 mr-1.5 ${size === "sm" ? "h-3 w-3 mr-1" : size === "lg" ? "h-5 w-5 mr-2" : ""}`} />
            Regenerate
          </button>
          
          <button
            onClick={() => handleAction('recrawl')}
            disabled={isAnyActionInProgress}
            className={`flex items-center px-3 py-1.5 text-sm border border-input rounded-md hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed ${
              size === "sm" ? "px-2 py-1 text-xs" : size === "lg" ? "px-4 py-2" : ""
            }`}
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${size === "sm" ? "h-3 w-3 mr-1" : size === "lg" ? "h-5 w-5 mr-2" : ""}`} />
            Recrawl
          </button>

          {showDelete && (
            <button
              onClick={() => handleAction('delete')}
              disabled={isAnyActionInProgress}
              className={`flex items-center px-3 py-1.5 text-sm text-destructive border border-destructive rounded-md hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed ${
                size === "sm" ? "px-2 py-1 text-xs" : size === "lg" ? "px-4 py-2" : ""
              }`}
            >
              <Trash2 className={`h-4 w-4 mr-1.5 ${size === "sm" ? "h-3 w-3 mr-1" : size === "lg" ? "h-5 w-5 mr-2" : ""}`} />
              Delete
            </button>
          )}
        </div>
        {actionDialogs}
      </>
    );
  }

  return (
    <>
      <div className="relative" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={isAnyActionInProgress}
          className="flex items-center px-2 py-1 text-sm text-muted-foreground hover:text-foreground border border-border rounded-md hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute right-0 top-full mt-1 w-48 bg-background border border-border rounded-md shadow-lg z-50">
              <div className="py-1">
                <button
                  onClick={() => handleAction('regenerate')}
                  disabled={isAnyActionInProgress}
                  className="flex items-center w-full px-3 py-2 text-sm text-left hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Sparkles className="h-4 w-4 mr-2 text-primary" />
                  Regenerate Descriptions
                </button>
                
                <button
                  onClick={() => handleAction('recrawl')}
                  disabled={isAnyActionInProgress}
                  className="flex items-center w-full px-3 py-2 text-sm text-left hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Recrawl Source
                </button>

                {showDelete && (
                  <div className="border-t border-border">
                    <button
                      onClick={() => handleAction('delete')}
                      disabled={isAnyActionInProgress}
                      className="flex items-center w-full px-3 py-2 text-sm text-left text-destructive hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete Source
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
      {actionDialogs}
    </>
  );
}