import React, { useState, useEffect, useRef } from "react";
import { Search, X, FileText, ExternalLink, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { FullPageModal } from "./FullPageModal";

interface DocumentSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentSearchModal: React.FC<DocumentSearchModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null);
  const [fullPageModalOpen, setFullPageModalOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setResults([]);
      setSelectedUrl(null);
    }
  }, [isOpen]);

  const performSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const response = await api.searchDocuments(searchQuery, { limit: 10 });
      setResults(response.results || []);
    } catch (error) {
      console.error("Search failed:", error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query]);

  const handleSelectDocument = (url: string) => {
    setSelectedUrl(url);
    setFullPageModalOpen(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 flex items-start justify-center bg-black/50 backdrop-blur-sm pt-20">
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-2xl mx-4">
          <div className="flex items-center gap-3 p-4 border-b dark:border-gray-700">
            <Search className="h-5 w-5 text-gray-400" />
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search pages by title, URL, or content..."
              className="flex-1 bg-transparent outline-none text-gray-900 dark:text-gray-100 placeholder-gray-500"
              autoFocus
            />
            {loading && (
              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
            )}
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-black"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {results.length > 0 ? (
              <div className="p-2">
                {results.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => handleSelectDocument(doc.url)}
                    className="w-full text-left p-3 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors group"
                  >
                    <div className="flex items-start gap-3">
                      <FileText className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">
                          {doc.title}
                        </h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                          {doc.url}
                        </p>
                        <div className="flex items-center gap-4 mt-1">
                          {doc.source_name && (
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              {doc.source_name}
                            </span>
                          )}
                          {doc.has_markdown && (
                            <span className="text-xs text-green-600 dark:text-green-400">
                              Full content available
                            </span>
                          )}
                        </div>
                      </div>
                      <ExternalLink className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>
                ))}
              </div>
            ) : query && !loading ? (
              <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                No documents found for "{query}"
              </div>
            ) : !query ? (
              <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                Start typing to search page titles, URLs, or content
              </div>
            ) : null}
          </div>

          {/* Footer */}
          {results.length > 0 && (
            <div className="px-4 py-2 border-t dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
              Found {results.length} result{results.length !== 1 ? "s" : ""}
            </div>
          )}
        </div>
      </div>

      {selectedUrl && (
        <FullPageModal
          url={selectedUrl}
          isOpen={fullPageModalOpen}
          onClose={() => {
            setFullPageModalOpen(false);
            setSelectedUrl(null);
          }}
          onNavigateToSnippets={() => {
            setFullPageModalOpen(false);
            setSelectedUrl(null);
            onClose();
          }}
        />
      )}
    </>
  );
};

