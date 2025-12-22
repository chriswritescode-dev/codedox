import React, { useState, useCallback, useEffect, useRef, useMemo, memo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../lib/api";
import { ConfirmationDialog } from "../ConfirmationDialog";
import { PaginationControls } from "../PaginationControls";
import { useToast } from "../../hooks/useToast";
import { useDebounce } from "../../hooks/useDebounce";
import { SourceGrid } from "./SourceGrid";
import { SearchBar } from "./SearchBar";
import { FilterDropdown } from "./FilterDropdown";
import { SelectionControls } from "./SelectionControls";
import { useSourcesData } from "./hooks/useSourcesData";
import { useSourceMutations } from "./hooks/useSourceMutations";
import { getSnippetBounds } from "./utils";

export const SourcesContent = memo(function SourcesContent() {
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();

  const snippetFilter = searchParams.get("filter") || "all";
  const currentPage = parseInt(searchParams.get("page") || "1", 10);
  const itemsPerPage = parseInt(searchParams.get("limit") || "20", 10);

  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const wasTypingRef = useRef(false);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(
    new Set()
  );
  const [isBulkDelete, setIsBulkDelete] = useState(false);
  const [isFilteredDelete, setIsFilteredDelete] = useState(false);
  const [filteredDeleteCount, setFilteredDeleteCount] = useState<number | null>(
    null
  );

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
        { replace: true }
      );
    },
    [setSearchParams]
  );

  useEffect(() => {
    if (searchQuery !== debouncedSearchQuery) {
      wasTypingRef.current = true;
    }
  }, [searchQuery, debouncedSearchQuery]);

  useEffect(() => {
    const currentQ = searchParams.get("q") || "";
    if (currentQ === debouncedSearchQuery) return;

    setSearchParams(
      (prev) => {
        const newParams = new URLSearchParams(prev);
        if (debouncedSearchQuery) {
          newParams.set("q", debouncedSearchQuery);
        } else {
          newParams.delete("q");
        }
        newParams.set("page", "1");
        return newParams;
      },
      { replace: true }
    );
  }, [debouncedSearchQuery, setSearchParams, searchParams]);

  const {
    data: sources,
    isLoading,
    error,
  } = useSourcesData({
    currentPage,
    itemsPerPage,
    debouncedSearchQuery,
    snippetFilter,
  });

  const {
    deleteMutation,
    bulkDeleteMutation,
    filteredDeleteMutation,
    updateSourceNameMutation,
    recrawlMutation,
    regenerateMutation,
  } = useSourceMutations();

  const filteredSources = useMemo(
    () => sources?.sources || [],
    [sources?.sources]
  );

  useEffect(() => {
    if (
      wasTypingRef.current &&
      searchInputRef.current &&
      searchQuery === debouncedSearchQuery
    ) {
      if (document.activeElement !== searchInputRef.current) {
        searchInputRef.current.focus();
      }
      wasTypingRef.current = false;
    }
  }, [sources, debouncedSearchQuery, searchQuery]);

  const handleBulkDelete = useCallback(async () => {
    const hasFilter = snippetFilter !== "all";
    const allFilteredSelected =
      selectedSources.size === sources?.total && sources?.total > 0;

    if (hasFilter && allFilteredSelected) {
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
        const bounds = getSnippetBounds(snippetFilter);
        filteredDeleteMutation.mutate({
          min_snippets: bounds.min,
          max_snippets: bounds.max,
          query: debouncedSearchQuery || undefined,
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
    snippetFilter,
    debouncedSearchQuery,
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
    const bounds = getSnippetBounds(snippetFilter);
    try {
      const result = await api.getFilteredSourceIds({
        query: debouncedSearchQuery || undefined,
        min_snippets: bounds.min,
        max_snippets: bounds.max,
      });
      setSelectedSources(new Set(result.ids));
    } catch (err) {
      console.error("Failed to fetch source IDs:", err);
      toast.error("Failed to select sources");
    }
  }, [snippetFilter, toast, debouncedSearchQuery]);

  const deselectAll = useCallback(() => {
    setSelectedSources(new Set());
  }, []);

  const handleUpdateSourceName = useCallback(
    async (id: string, newName: string, newVersion?: string) => {
      await updateSourceNameMutation.mutateAsync({
        id,
        name: newName,
        version: newVersion,
      });
    },
    [updateSourceNameMutation]
  );

  const handlePageChange = useCallback(
    (page: number) => {
      updateUrlParams({ page: page.toString() });
    },
    [updateUrlParams]
  );

  const handleItemsPerPageChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newItemsPerPage = parseInt(e.target.value);
      updateUrlParams({
        limit: newItemsPerPage.toString(),
        page: "1",
      });
    },
    [updateUrlParams]
  );

  const handleFilterChange = useCallback(
    (value: string) => {
      updateUrlParams({
        filter: value === "all" ? null : value,
        page: "1",
      });
    },
    [updateUrlParams]
  );

  const handleRecrawl = useCallback(
    (sourceId: string, options?: { ignoreHash?: boolean }) => {
      recrawlMutation.mutate({
        sourceId,
        ignoreHash: options?.ignoreHash || false,
      });
    },
    [recrawlMutation]
  );

  const handleRegenerate = useCallback(
    (sourceId: string) => {
      regenerateMutation.mutate(sourceId);
    },
    [regenerateMutation]
  );

  const handleDelete = useCallback(
    (sourceId: string) => {
      const source = filteredSources.find((s) => s.id === sourceId);
      if (source) {
        setSourceToDelete(source);
        setIsBulkDelete(false);
        setDeleteModalOpen(true);
      }
    },
    [filteredSources]
  );

  const handleCancelDelete = useCallback(() => {
    setDeleteModalOpen(false);
    setIsBulkDelete(false);
    setIsFilteredDelete(false);
    setFilteredDeleteCount(null);
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
    <>
      <div className="flex gap-4 items-center">
        <SearchBar
          ref={searchInputRef}
          value={searchQuery}
          onChange={setSearchQuery}
        />

        <FilterDropdown value={snippetFilter} onChange={handleFilterChange} />

        <SelectionControls
          selectedCount={selectedSources.size}
          totalCount={sources?.total || 0}
          onSelectAll={selectAll}
          onDeselectAll={deselectAll}
          onBulkDelete={handleBulkDelete}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-auto pb-4 mt-4">
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
          <SourceGrid
            sources={filteredSources}
            selectedSources={selectedSources}
            onToggleSelect={toggleSelectSource}
            onDelete={handleDelete}
            onRecrawl={handleRecrawl}
            onRegenerate={handleRegenerate}
            onUpdateName={handleUpdateSourceName}
            isPendingRecrawl={recrawlMutation.isPending}
            isPendingRegenerate={regenerateMutation.isPending}
            isPendingDelete={deleteMutation.isPending}
          />
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
        onCancel={handleCancelDelete}
      />

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
    </>
  );
});
