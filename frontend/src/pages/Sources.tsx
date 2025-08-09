import React, { useState, useEffect, useCallback, memo, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FileText, Code, Trash2, X, Search, Check, RefreshCw, Filter } from 'lucide-react'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { EditableSourceName } from '../components/EditableSourceName'
import { RecrawlDialog } from '../components/RecrawlDialog'
import { PaginationControls } from '../components/PaginationControls'

// Memoized source card component
const SourceCard = ({ 
  source, 
  isSelected, 
  onToggleSelect, 
  onDelete, 
  onRecrawl,
  onUpdateName,
  isPendingRecrawl
}: {
  source: any;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
  onDelete: (e: React.MouseEvent, source: { id: string; name: string }) => void;
  onRecrawl: (e: React.MouseEvent, source: { id: string; name: string; base_url: string }) => void;
  onUpdateName: (id: string, name: string) => Promise<void>;
  isPendingRecrawl: boolean;
}) => {
  const navigate = useNavigate();
  
  const handleCardClick = (e: React.MouseEvent) => {
    // Don't navigate if clicking on interactive elements
    const target = e.target as HTMLElement;
    const isInteractive = target.closest('button, input, a, [role="button"]');
    if (!isInteractive) {
      navigate(`/sources/${source.id}`);
    }
  };

  return (
    <div
      className={`relative bg-secondary/50 rounded-lg p-6 hover:bg-secondary transition-colors group cursor-pointer ${
        isSelected ? "ring-2 ring-primary" : ""
      }`}
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
          className={`w-5 h-5 rounded border-2 flex items-center justify-center cursor-pointer ${
            isSelected
              ? "bg-primary border-primary"
              : "border-input bg-background hover:border-primary"
          }`}
        >
          {isSelected && (
            <Check className="h-3 w-3 text-primary-foreground" />
          )}
        </div>
      </div>

      <div className="flex items-start justify-between mb-4 pl-8">
        <span className="text-xs text-muted-foreground">
          {new Date(source.created_at).toLocaleDateString()}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRecrawl(e, source);
            }}
            className="p-1 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
            title="Recrawl source"
            disabled={isPendingRecrawl}
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(e, source);
            }}
            className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
            title="Delete source"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mb-4 pl-8">
        <div 
          onClick={(e) => e.stopPropagation()}
          className="inline-block"
        >
          <EditableSourceName
            id={source.id}
            name={source.name}
            onUpdate={onUpdateName}
            className="text-lg font-medium"
          />
        </div>
        <div className="text-xs text-muted-foreground mt-1 truncate">
          {source.base_url}
        </div>
      </div>

      <div className="flex items-center justify-between pl-8">
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
      </div>
    </div>
  );
};

SourceCard.displayName = 'SourceCard';

const SourceGrid = memo(({ 
  sources, 
  selectedSources,
  onToggleSelect,
  onDelete,
  onRecrawl,
  onUpdateName,
  isPendingRecrawl
}: {
  sources: any[];
  selectedSources: Set<string>;
  onToggleSelect: (id: string) => void;
  onDelete: (e: React.MouseEvent, source: { id: string; name: string }) => void;
  onRecrawl: (e: React.MouseEvent, source: { id: string; name: string; base_url: string }) => void;
  onUpdateName: (id: string, name: string) => Promise<void>;
  isPendingRecrawl: boolean;
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sources.map((source: any) => (
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
  );
});

SourceGrid.displayName = 'SourceGrid';

export default function Sources() {
  const [searchParams, setSearchParams] = useSearchParams();
  const searchInputRef = useRef<HTMLInputElement>(null);
  
  // Get values from URL params
  const searchQuery = searchParams.get('q') || '';
  const snippetFilter = searchParams.get('filter') || 'all';
  const currentPage = parseInt(searchParams.get('page') || '1', 10);
  const itemsPerPage = parseInt(searchParams.get('limit') || '10', 10);
  
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState(searchQuery);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(
    new Set()
  );
  const [isBulkDelete, setIsBulkDelete] = useState(false);
  const [recrawlDialogOpen, setRecrawlDialogOpen] = useState(false);
  const [sourceToRecrawl, setSourceToRecrawl] = useState<{
    id: string;
    name: string;
    base_url: string;
  } | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  
  // Update URL params helper
  const updateUrlParams = useCallback((updates: Record<string, string | null>) => {
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === '') {
          newParams.delete(key);
        } else {
          newParams.set(key, value);
        }
      });
      return newParams;
    }, { replace: true });
  }, [setSearchParams]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);
  
  // Maintain input focus after debounce
  useEffect(() => {
    // Keep focus on search input if it was focused
    if (document.activeElement === searchInputRef.current) {
      searchInputRef.current?.focus();
    }
  }, [debouncedSearchQuery]);

  // Calculate snippet filter bounds
  const getSnippetBounds = useCallback(() => {
    switch(snippetFilter) {
      case '0': return { min: 0, max: 0 };
      case '1-10': return { min: 1, max: 10 };
      case '11-50': return { min: 11, max: 50 };
      case '51-100': return { min: 51, max: 100 };
      case '100+': return { min: 101, max: undefined };
      default: return { min: undefined, max: undefined };
    }
  }, [snippetFilter]);

  const {
    data: sources,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["sources", currentPage, itemsPerPage, debouncedSearchQuery, snippetFilter],
    queryFn: () => {
      const offset = (currentPage - 1) * itemsPerPage;
      const bounds = getSnippetBounds();
      
      // Use search API if there's a query or filter
      if (debouncedSearchQuery || snippetFilter !== 'all') {
        return api.searchSources({
          query: debouncedSearchQuery || undefined,
          min_snippets: bounds.min,
          max_snippets: bounds.max,
          limit: itemsPerPage,
          offset
        });
      }
      
      // Use regular getSources for unfiltered results
      return api.getSources({ limit: itemsPerPage, offset });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => api.deleteSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setDeleteModalOpen(false);
      setSourceToDelete(null);
    },
    onError: (error) => {
      console.error("Failed to delete source:", error);
      alert(
        "Failed to delete source: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (sourceIds: string[]) => api.deleteBulkSources(sourceIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setDeleteModalOpen(false);
      setSelectedSources(new Set());
      setIsBulkDelete(false);
    },
    onError: (error) => {
      console.error("Failed to delete sources:", error);
      alert(
        "Failed to delete sources: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const updateSourceNameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.updateSourceName(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error) => {
      console.error("Failed to update source name:", error);
      throw error; // Re-throw so the component can handle it
    },
  });

  const recrawlMutation = useMutation({
    mutationFn: ({ sourceId, ignoreHash }: { sourceId: string; ignoreHash: boolean }) => 
      api.recrawlSource(sourceId, ignoreHash),
    onSuccess: (data) => {
      setRecrawlDialogOpen(false);
      setSourceToRecrawl(null);
      // Navigate to the crawl detail page for the new crawl job
      navigate(`/crawl/${data.id}`);
    },
    onError: (error) => {
      console.error("Failed to recrawl source:", error);
      alert(
        "Failed to recrawl source: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  // Sources are now filtered server-side
  const filteredSources = sources?.sources || [];

  const handleDeleteClick = useCallback((
    e: React.MouseEvent,
    source: { id: string; name: string }
  ) => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation(); // Prevent checkbox toggle
    setSourceToDelete(source);
    setIsBulkDelete(false);
    setDeleteModalOpen(true);
  }, []);

  const handleBulkDelete = useCallback(() => {
    setIsBulkDelete(true);
    setDeleteModalOpen(true);
  }, []);

  const confirmDelete = useCallback(() => {
    if (isBulkDelete) {
      bulkDeleteMutation.mutate(Array.from(selectedSources));
    } else if (sourceToDelete) {
      deleteMutation.mutate(sourceToDelete.id);
    }
  }, [isBulkDelete, selectedSources, sourceToDelete, bulkDeleteMutation, deleteMutation]);

  const toggleSelectSource = useCallback((sourceId: string) => {
    setSelectedSources(prev => {
      const newSelected = new Set(prev);
      if (newSelected.has(sourceId)) {
        newSelected.delete(sourceId);
      } else {
        newSelected.add(sourceId);
      }
      return newSelected;
    });
  }, []);

  const selectAll = useCallback(() => {
    const allIds = new Set(filteredSources.map((s: any) => s.id));
    setSelectedSources(allIds as Set<string>);
  }, [filteredSources]);

  const deselectAll = useCallback(() => {
    setSelectedSources(new Set());
  }, []);

  const handleUpdateSourceName = useCallback(async (id: string, newName: string) => {
    await updateSourceNameMutation.mutateAsync({ id, name: newName });
  }, [updateSourceNameMutation]);

  const handlePageChange = useCallback((page: number) => {
    updateUrlParams({ page: page.toString() });
  }, [updateUrlParams]);

  const handleItemsPerPageChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const newItemsPerPage = parseInt(e.target.value);
    updateUrlParams({ 
      limit: newItemsPerPage.toString(),
      page: '1' // Reset to first page when changing items per page
    });
  }, [updateUrlParams]);
  
  const handleSearchChange = useCallback((value: string) => {
    updateUrlParams({ 
      q: value || null,
      page: '1' // Reset to first page on search
    });
  }, [updateUrlParams]);
  
  const handleFilterChange = useCallback((value: string) => {
    updateUrlParams({ 
      filter: value === 'all' ? null : value,
      page: '1' // Reset to first page on filter change
    });
  }, [updateUrlParams]);

  const handleRecrawlClick = useCallback((
    e: React.MouseEvent,
    source: { id: string; name: string; base_url: string }
  ) => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation(); // Prevent checkbox toggle
    setSourceToRecrawl(source);
    setRecrawlDialogOpen(true);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading sources...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">
          Error loading sources:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full">
      <div className="flex-1 space-y-6 pb-6">
        <div>
          <h1 className="text-3xl font-bold">Documentation Sources</h1>
          <p className="text-muted-foreground mt-2">
            Browse all crawled documentation sources
          </p>
        </div>

      <div className="space-y-4">
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search sources by name or URL"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {searchQuery && (
              <button
                onClick={() => handleSearchChange('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={snippetFilter}
              onChange={(e) => handleFilterChange(e.target.value)}
              className="px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">All Snippets</option>
              <option value="0">No Snippets</option>
              <option value="1-10">1-10 Snippets</option>
              <option value="11-50">11-50 Snippets</option>
              <option value="51-100">51-100 Snippets</option>
              <option value="100+">100+ Snippets</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-md">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div
                onClick={() => {
                  if (
                    selectedSources.size === filteredSources.length &&
                    filteredSources.length > 0
                  ) {
                    deselectAll();
                  } else {
                    selectAll();
                  }
                }}
                className="cursor-pointer"
              >
                <div
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                    selectedSources.size === filteredSources.length &&
                    filteredSources.length > 0
                      ? "bg-primary border-primary"
                      : selectedSources.size > 0 &&
                        selectedSources.size < filteredSources.length
                      ? "bg-primary/50 border-primary"
                      : "border-input bg-background"
                  }`}
                >
                  {selectedSources.size === filteredSources.length &&
                    filteredSources.length > 0 && (
                      <Check className="h-3 w-3 text-primary-foreground" />
                    )}
                  {selectedSources.size > 0 &&
                    selectedSources.size < filteredSources.length && (
                      <div className="w-2 h-2 bg-primary-foreground rounded-sm" />
                    )}
                </div>
              </div>
              <span className="text-sm font-medium">
                {selectedSources.size} of {filteredSources.length} selected
              </span>
            </div>
            <button
              onClick={selectAll}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Select all {(debouncedSearchQuery || snippetFilter !== 'all') && "filtered"}
            </button>
            {selectedSources.size > 0 && (
              <>
                <span className="text-muted-foreground">•</span>
                <button
                  onClick={deselectAll}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Clear selection
                </button>
              </>
            )}
          </div>
          <button
            onClick={handleBulkDelete}
            disabled={selectedSources.size === 0}
            className={`px-4 py-2 rounded-md transition-colors ${
              selectedSources.size > 0
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : "bg-secondary text-muted-foreground cursor-not-allowed"
            }`}
          >
            Delete Selected
          </button>
        </div>
      </div>

      {sources && (sources as any).sources.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No sources found. Start by crawling some documentation.
        </div>
      )}

      {filteredSources.length === 0 && sources && (sources as any).sources.length > 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No sources match your search.
        </div>
      )}

      {filteredSources.length > 0 && (
        <SourceGrid
          sources={filteredSources}
          selectedSources={selectedSources}
          onToggleSelect={toggleSelectSource}
          onDelete={handleDeleteClick}
          onRecrawl={handleRecrawlClick}
          onUpdateName={handleUpdateSourceName}
          isPendingRecrawl={recrawlMutation.isPending}
        />
      )}

      <ConfirmationDialog
        isOpen={deleteModalOpen}
        title="Confirm Delete"
        message={
          isBulkDelete
            ? `Are you sure you want to delete ${selectedSources.size} source${
                selectedSources.size > 1 ? "s" : ""
              }? This will permanently remove all associated documents and code snippets.`
            : `Are you sure you want to delete the source "${sourceToDelete?.name}"? This will permanently remove all associated documents and code snippets.`
        }
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={deleteMutation.isPending || bulkDeleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => {
          setDeleteModalOpen(false);
          setIsBulkDelete(false);
        }}
      />

      {sourceToRecrawl && (
        <RecrawlDialog
          isOpen={recrawlDialogOpen}
          sourceName={sourceToRecrawl.name}
          sourceUrl={sourceToRecrawl.base_url}
          onConfirm={(ignoreHash) => {
            recrawlMutation.mutate({ sourceId: sourceToRecrawl.id, ignoreHash });
          }}
          onCancel={() => {
            setRecrawlDialogOpen(false);
            setSourceToRecrawl(null);
          }}
          isRecrawling={recrawlMutation.isPending}
        />
      )}

      </div>

      {/* Pagination Controls */}
      {sources && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label htmlFor="items-per-page" className="text-sm text-muted-foreground">
                  Items per page:
                </label>
                <select
                  id="items-per-page"
                  value={itemsPerPage}
                  onChange={handleItemsPerPageChange}
                  className="w-20 px-2 py-1 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
          </div>
          
          <PaginationControls
            currentPage={currentPage}
            totalPages={Math.ceil((sources as any).total / itemsPerPage)}
            onPageChange={handlePageChange}
            totalItems={(sources as any).total}
            itemsPerPage={itemsPerPage}
            currentItemsCount={filteredSources.length}
          />
        </div>
      )}
    </div>
  );
}
