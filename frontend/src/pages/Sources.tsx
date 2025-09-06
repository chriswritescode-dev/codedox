import React, { useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { RecrawlDialog } from '../components/RecrawlDialog'
import { PaginationControls } from '../components/PaginationControls'
import { useToast } from '../hooks/useToast'
import { SourceGrid } from "../components/sources/SourceGrid";
import { SearchBar } from "../components/sources/SearchBar";
import { FilterDropdown } from "../components/sources/FilterDropdown";
import { SelectionControls } from "../components/sources/SelectionControls";
import { useSourcesData } from "../components/sources/hooks/useSourcesData";
import { useSourceMutations } from "../components/sources/hooks/useSourceMutations";

export default function Sources() {
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();

  const snippetFilter = searchParams.get("filter") || "all";
  const currentPage = parseInt(searchParams.get("page") || "1", 10);
  const itemsPerPage = parseInt(searchParams.get("limit") || "20", 10);
  const searchQuery = searchParams.get("q") || "";

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(
    new Set(),
  );
  const [isBulkDelete, setIsBulkDelete] = useState(false);
  const [isFilteredDelete, setIsFilteredDelete] = useState(false);
  const [filteredDeleteCount, setFilteredDeleteCount] = useState<number | null>(
    null,
  );
  const [recrawlDialogOpen, setRecrawlDialogOpen] = useState(false);
  const [sourceToRecrawl, setSourceToRecrawl] = useState<{
    id: string;
    name: string;
    base_url: string;
  } | null>(null);

  const updateUrlParams = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(
        (prev) => {
          const newParams = new URLSearchParams(prev);
          Object.entries(updates).forEach(([key, value]) => {
            if (value === null || value === "") {
              newParams.delete(key);
            } else {
              newParams.set(key, value);
            }
          });
          return newParams;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const getSnippetBounds = useCallback(() => {
    switch (snippetFilter) {
      case "0":
        return { min: 0, max: 0 };
      case "has-snippets":
        return { min: 1, max: undefined };
      default:
        return { min: undefined, max: undefined };
    }
  }, [snippetFilter]);

  const {
    data: sources,
    isLoading,
    error,
  } = useSourcesData({
    currentPage,
    itemsPerPage,
    debouncedSearchQuery: searchQuery,
    snippetFilter,
  });

  const {
    deleteMutation,
    bulkDeleteMutation,
    filteredDeleteMutation,
    updateSourceNameMutation,
    recrawlMutation,
  } = useSourceMutations();

  // Sources are now filtered server-side
  const filteredSources = sources?.sources || [];

  const handleDeleteClick = useCallback(
    (e: React.MouseEvent, source: { id: string; name: string }) => {
      e.preventDefault(); // Prevent navigation
      e.stopPropagation(); // Prevent checkbox toggle
      setSourceToDelete(source);
      setIsBulkDelete(false);
      setDeleteModalOpen(true);
    },
    [],
  );

  const handleBulkDelete = useCallback(async () => {
    // Check if all sources matching the filter are selected
    const hasFilter = snippetFilter !== "all";
    const allFilteredSelected =
      selectedSources.size === sources?.total && sources?.total > 0;

    if (hasFilter && allFilteredSelected) {
      // All filtered sources are selected - use filtered delete
      setFilteredDeleteCount(selectedSources.size);
      setIsFilteredDelete(true);
    } else {
      setIsFilteredDelete(false);
      setFilteredDeleteCount(null);
    }

    setIsBulkDelete(true);
    setDeleteModalOpen(true);
  }, [snippetFilter, selectedSources.size, sources?.total]);

  const confirmDelete = useCallback(() => {
    if (isBulkDelete) {
      if (isFilteredDelete) {
        const bounds = getSnippetBounds();
        filteredDeleteMutation.mutate({
          min_snippets: bounds.min,
          max_snippets: bounds.max,
          query: searchQuery || undefined,
        });
      } else {
        bulkDeleteMutation.mutate(Array.from(selectedSources));
      }
    } else if (sourceToDelete) {
      deleteMutation.mutate(sourceToDelete.id);
    }

    setDeleteModalOpen(false);
    setSourceToDelete(null);
    setSelectedSources(new Set());
    setIsBulkDelete(false);
    setIsFilteredDelete(false);
    setFilteredDeleteCount(null);
  }, [
    isBulkDelete,
    isFilteredDelete,
    selectedSources,
    sourceToDelete,
    bulkDeleteMutation,
    filteredDeleteMutation,
    deleteMutation,
    getSnippetBounds,
    searchQuery,
  ]);

  const toggleSelectSource = useCallback((sourceId: string) => {
    setSelectedSources((prev) => {
      const newSelected = new Set(prev);
      if (newSelected.has(sourceId)) {
        newSelected.delete(sourceId);
      } else {
        newSelected.add(sourceId);
      }
      return newSelected;
    });
  }, []);

  const selectAll = useCallback(async () => {
    // Fetch ALL source IDs matching current filters
    const bounds = getSnippetBounds();
    try {
      const result = await api.getFilteredSourceIds({
        query: searchQuery || undefined,
        min_snippets: bounds.min,
        max_snippets: bounds.max,
      });
      setSelectedSources(new Set(result.ids));
    } catch (error) {
      console.error("Failed to fetch source IDs:", error);
      toast.error("Failed to select sources");
    }
  }, [getSnippetBounds, toast, searchQuery]);

  const deselectAll = useCallback(() => {
    setSelectedSources(new Set());
  }, []);

  const handleUpdateSourceName = useCallback(
    async (id: string, newName: string, newVersion?: string) => {
      await updateSourceNameMutation.mutateAsync({ 
        id, 
        name: newName, 
        version: newVersion 
      });
    },
    [updateSourceNameMutation],
  );

  const handlePageChange = useCallback(
    (page: number) => {
      updateUrlParams({ page: page.toString() });
    },
    [updateUrlParams],
  );

  const handleItemsPerPageChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newItemsPerPage = parseInt(e.target.value);
      updateUrlParams({
        limit: newItemsPerPage.toString(),
        page: "1", // Reset to first page when changing items per page
      });
    },
    [updateUrlParams],
  );

  const handleSearchChange = useCallback((value: string) => {
    updateUrlParams({
      q: value || null,
      page: "1", // Reset to first page on search
    });
  }, [updateUrlParams]);

  const handleFilterChange = useCallback(
    (value: string) => {
      updateUrlParams({
        filter: value === "all" ? null : value,
        page: "1", // Reset to first page on filter change
      });
    },
    [updateUrlParams],
  );

  const handleRecrawlClick = useCallback(
    (
      e: React.MouseEvent,
      source: { id: string; name: string; base_url: string },
    ) => {
      e.preventDefault();
      e.stopPropagation();
      setSourceToRecrawl(source);
      setRecrawlDialogOpen(true);
    },
    [],
  );

  const handleRecrawlConfirm = useCallback(
    (ignoreHash: boolean) => {
      if (sourceToRecrawl) {
        recrawlMutation.mutate({
          sourceId: sourceToRecrawl.id,
          ignoreHash,
        });
        setRecrawlDialogOpen(false);
        setSourceToRecrawl(null);
      }
    },
    [sourceToRecrawl, recrawlMutation],
  );

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
    <div className="flex flex-col h-full w-full min-h-0">
      {/* Fixed header section */}
      <div className="space-y-4 pb-4">
        <div>
          <h1 className="text-3xl font-bold">Documentation Sources</h1>
        </div>

        <div className="flex gap-4 items-center">
          <SearchBar onChange={handleSearchChange} />

          <FilterDropdown value={snippetFilter} onChange={handleFilterChange} />

          <SelectionControls
            selectedCount={selectedSources.size}
            totalCount={sources?.total || 0}
            onSelectAll={selectAll}
            onDeselectAll={deselectAll}
            onBulkDelete={handleBulkDelete}
          />
        </div>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 min-h-0 overflow-auto pb-4">
        {sources && sources.sources.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            No sources found. Start by crawling some documentation.
          </div>
        )}

        {filteredSources.length === 0 &&
          sources &&
          sources.sources.length > 0 && (
            <div className="text-center py-12 text-muted-foreground">
              No sources match your search.
            </div>
          )}

        {filteredSources.length > 0 && (
          <div className="">
            <SourceGrid
              sources={filteredSources}
              selectedSources={selectedSources}
              onToggleSelect={toggleSelectSource}
              onDelete={handleDeleteClick}
              onRecrawl={handleRecrawlClick}
              onUpdateName={handleUpdateSourceName}
              isPendingRecrawl={recrawlMutation.isPending}
            />
          </div>
        )}
      </div>

      <ConfirmationDialog
        isOpen={deleteModalOpen}
        title="Confirm Delete"
        message={
          isBulkDelete
            ? isFilteredDelete && filteredDeleteCount !== null
              ? `Are you sure you want to delete ALL ${filteredDeleteCount} source${
                  filteredDeleteCount > 1 ? "s" : ""
                } matching the current filter? This will permanently remove all associated documents and code snippets.`
              : `Are you sure you want to delete ${selectedSources.size} source${
                  selectedSources.size > 1 ? "s" : ""
                }? This will permanently remove all associated documents and code snippets.`
            : `Are you sure you want to delete the source "${sourceToDelete?.name}"? This will permanently remove all associated documents and code snippets.`
        }
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={
          deleteMutation.isPending ||
          bulkDeleteMutation.isPending ||
          filteredDeleteMutation.isPending
        }
        onConfirm={confirmDelete}
        onCancel={() => {
          setDeleteModalOpen(false);
          setIsBulkDelete(false);
          setIsFilteredDelete(false);
          setFilteredDeleteCount(null);
        }}
      />

      {sourceToRecrawl && (
        <RecrawlDialog
          isOpen={recrawlDialogOpen}
          sourceName={sourceToRecrawl.name}
          sourceUrl={sourceToRecrawl.base_url}
          onConfirm={handleRecrawlConfirm}
          onCancel={() => {
            setRecrawlDialogOpen(false);
            setSourceToRecrawl(null);
          }}
          isRecrawling={recrawlMutation.isPending}
        />
      )}

      {/* Pagination Controls */}
      {sources && (
        <div className="pt-4 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label
                htmlFor="items-per-page"
                className="text-sm text-muted-foreground"
              >
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

          <PaginationControls
            currentPage={currentPage}
            totalPages={Math.ceil(sources.total / itemsPerPage)}
            onPageChange={handlePageChange}
            totalItems={sources.total}
            itemsPerPage={itemsPerPage}
            currentItemsCount={filteredSources.length}
          />
        </div>
      )}
    </div>
  );
}
