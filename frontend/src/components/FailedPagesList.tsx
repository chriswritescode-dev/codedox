import { useState } from "react";
import { XCircle, AlertCircle, RefreshCw } from "lucide-react";

interface FailedPage {
  id: number;
  url: string;
  error_message: string | null;
  failed_at: string | null;
}

interface FailedPagesListProps {
  pages: FailedPage[];
  onRetrySelected: (urls: string[]) => void;
  isRetrying?: boolean;
}

export function FailedPagesList({ pages, onRetrySelected, isRetrying = false }: FailedPagesListProps) {
  const [selectedPages, setSelectedPages] = useState<Set<number>>(new Set());

  const handleTogglePage = (pageId: number) => {
    const newSelected = new Set(selectedPages);
    if (newSelected.has(pageId)) {
      newSelected.delete(pageId);
    } else {
      newSelected.add(pageId);
    }
    setSelectedPages(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedPages.size === pages.length) {
      setSelectedPages(new Set());
    } else {
      setSelectedPages(new Set(pages.map((p) => p.id)));
    }
  };

  const handleRetry = () => {
    const selectedUrls = pages
      .filter((page) => selectedPages.has(page.id))
      .map((page) => page.url);
    
    if (selectedUrls.length > 0) {
      onRetrySelected(selectedUrls);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-3">
        <div className="flex items-center gap-2">
          <XCircle className="h-5 w-5 text-red-500" />
          <h3 className="text-lg font-semibold">Failed Pages ({pages.length})</h3>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSelectAll}
            className="text-sm px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            {selectedPages.size === pages.length ? "Deselect All" : "Select All"}
          </button>
          <button
            onClick={handleRetry}
            disabled={selectedPages.size === 0 || isRetrying}
            className="flex items-center gap-2 px-3 py-1 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`h-4 w-4 ${isRetrying ? "animate-spin" : ""}`} />
            Retry Selected ({selectedPages.size})
          </button>
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {pages.map((page) => (
          <div
            key={page.id}
            className={`p-3 border rounded-md cursor-pointer transition-colors ${
              selectedPages.has(page.id)
                ? "border-primary bg-primary/5"
                : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
            }`}
            onClick={() => handleTogglePage(page.id)}
          >
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={selectedPages.has(page.id)}
                onChange={() => handleTogglePage(page.id)}
                onClick={(e) => e.stopPropagation()}
                className="mt-1"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{page.url}</p>
                {page.error_message && (
                  <div className="flex items-start gap-1 mt-1">
                    <AlertCircle className="h-3 w-3 text-red-500 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-red-600 dark:text-red-400">{page.error_message}</p>
                  </div>
                )}
                {page.failed_at && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Failed at: {new Date(page.failed_at).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}