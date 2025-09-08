import { useRef, useEffect } from "react";
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  FileText,
  Code,
  ExternalLink,
  Search,
  X,
} from "lucide-react";
import { SnippetList } from '../components/SnippetList'
import { PaginationControls } from '../components/PaginationControls'
import { useDocumentDetail } from "../hooks/useDocumentDetail";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function DocumentDetail() {
  const { sourceId, documentId } = useParams<{
    sourceId: string;
    documentId: string;
  }>();
  const state = useDocumentDetail(sourceId, documentId);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const wasTypingRef = useRef(false);

  // Track when user is actively typing (before debounce)
  useEffect(() => {
    if (state.searchQuery !== state.debouncedSearchQuery) {
      wasTypingRef.current = true;
    }
  }, [state.searchQuery, state.debouncedSearchQuery]);

  useEffect(() => {
    if (
      wasTypingRef.current &&
      searchInputRef.current &&
      state.searchQuery === state.debouncedSearchQuery
    ) {
      if (document.activeElement !== searchInputRef.current) {
        searchInputRef.current.focus();
      }
      wasTypingRef.current = false;
    }
  }, [state.data, state.debouncedSearchQuery]);

  if (state.isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">
          Loading document snippets...
        </div>
      </div>
    );
  }

  if (state.error || !state.data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive mb-2">
            Document Not Found
          </h1>
          <p className="text-muted-foreground mb-4">
            This document may have been deleted or never existed.
          </p>
          <Link
            to={`/sources/${sourceId}`}
            className="inline-flex items-center text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to source
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Fixed header section */}
      <div className="space-y-6 pb-4">
        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-2 text-sm">
          <Link
            to="/sources"
            className="text-muted-foreground hover:text-foreground"
          >
            Sources
          </Link>
          <span className="text-muted-foreground">/</span>
          {state.data.source && (
            <>
              <Link
                to={`/sources/${state.data.source.id}`}
                className="text-muted-foreground hover:text-foreground"
              >
                {state.data.source.name}
              </Link>
              <span className="text-muted-foreground">/</span>
            </>
          )}
          <span className="text-foreground">Document</span>
        </div>

        {/* Document header */}
        <div className="bg-secondary/50 rounded-lg p-6">
          <div className="flex items-start gap-3 mb-4">
            <FileText className="h-8 w-8 text-muted-foreground mt-1" />
            <div className="flex-1">
              <h1 className="text-2xl font-bold mb-2">
                {state.data.document.title}
              </h1>
              <a
                href={state.data.document.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              >
                {state.data.document.url}
                <ExternalLink className="h-3 w-3" />
              </a>
              <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                <span>Depth: {state.data.document.crawl_depth}</span>
                <span>•</span>
                <span>
                  {new Date(
                    state.data.document.created_at,
                  ).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-6 pt-4 border-t border-border">
            <div className="flex items-center gap-4">
              <Code className="h-5 w-5 text-muted-foreground" />

              <div className="flex items-center gap-2">
                <div className="text-2xl font-semibold">{state.data.total}</div>
                <div className="text-sm text-muted-foreground">
                  Code Snippets
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Search/Filter controls - always visible */}
        <div className="px-2 pb-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex gap-3 flex-1 min-w-0">
              <div className="flex-1 relative min-w-[300px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search snippets in this document..."
                  value={state.searchQuery}
                  onChange={(e) => state.setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                {state.searchQuery && (
                  <>
                    <span className="absolute right-12 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                      {state.data && state.data.total > 0
                        ? `(${state.data.total} matches)`
                        : "(0 matches)"}
                    </span>
                    <button
                      onClick={() => state.setSearchQuery("")}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </>
                )}
              </div>

              {state.languages && state.languages.languages.length > 0 && (
                <Select
                  value={state.selectedLanguage || "all"}
                  onValueChange={(value) => {
                    state.setSelectedLanguage(value === "all" ? "" : value);
                    state.setCurrentPage(1);
                  }}
                >
                  <SelectTrigger className="w-[180px] h-[42px]!">
                    <SelectValue placeholder="All Languages" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Languages</SelectItem>
                    {state.languages.languages.map((lang: any) => (
                      <SelectItem key={lang.name} value={lang.name}>
                        {lang.name} ({lang.count})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 min-h-0 overflow-auto pb-4">
        <div className="mx-auto w-full">
          {/* Snippets */}
          {state.data.snippets.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              {state.debouncedSearchQuery || state.selectedLanguage
                ? "No snippets match your filters."
                : "No code snippets found in this document."}
            </div>
          ) : (
            <>
              <SnippetList snippets={state.data.snippets} />
            </>
          )}
        </div>
      </div>

      {/* Pagination Controls - Always visible at bottom */}
      {state.data && (
        <div className="pt-4 border-t border-border">
          <PaginationControls
            currentPage={state.currentPage}
            totalPages={state.totalPages}
            onPageChange={state.setCurrentPage}
            totalItems={state.data.total}
            itemsPerPage={state.itemsPerPage}
            currentItemsCount={state.data.snippets.length}
          />
        </div>
      )}
    </div>
  );
}
