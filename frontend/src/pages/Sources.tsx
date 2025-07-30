import React, { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Link, useNavigate } from 'react-router-dom'
import { Database, FileText, Code, Trash2, X, Search, Check, RefreshCw } from 'lucide-react'
import { ConfirmationDialog } from '../components/ConfirmationDialog'
import { EditableSourceName } from '../components/EditableSourceName'
import { RecrawlDialog } from '../components/RecrawlDialog'

export default function Sources() {
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
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

  const {
    data: sources,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["sources"],
    queryFn: () => {
      console.log("Fetching sources...");
      return api.getSources();
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

  // Filter sources based on search query
  const filteredSources = useMemo(() => {
    if (!sources) return [];
    if (!searchQuery) return sources;

    const query = searchQuery.toLowerCase();
    return sources.filter(
      (source) =>
        source.name.toLowerCase().includes(query) ||
        source.base_url.toLowerCase().includes(query)
    );
  }, [sources, searchQuery]);

  const handleDeleteClick = (
    e: React.MouseEvent,
    source: { id: string; name: string }
  ) => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation(); // Prevent checkbox toggle
    setSourceToDelete(source);
    setIsBulkDelete(false);
    setDeleteModalOpen(true);
  };

  const handleBulkDelete = () => {
    setIsBulkDelete(true);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (isBulkDelete) {
      bulkDeleteMutation.mutate(Array.from(selectedSources));
    } else if (sourceToDelete) {
      deleteMutation.mutate(sourceToDelete.id);
    }
  };

  const toggleSelectSource = (sourceId: string) => {
    const newSelected = new Set(selectedSources);
    if (newSelected.has(sourceId)) {
      newSelected.delete(sourceId);
    } else {
      newSelected.add(sourceId);
    }
    setSelectedSources(newSelected);
  };

  const selectAll = () => {
    const allIds = new Set(filteredSources.map((s) => s.id));
    setSelectedSources(allIds);
  };

  const deselectAll = () => {
    setSelectedSources(new Set());
  };

  const handleUpdateSourceName = async (id: string, newName: string) => {
    await updateSourceNameMutation.mutateAsync({ id, name: newName });
  };

  const handleRecrawlClick = (
    e: React.MouseEvent,
    source: { id: string; name: string; base_url: string }
  ) => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation(); // Prevent checkbox toggle
    setSourceToRecrawl(source);
    setRecrawlDialogOpen(true);
  };

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
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Documentation Sources</h1>
        <p className="text-muted-foreground mt-2">
          Browse all crawled documentation sources
        </p>
      </div>

      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search sources by name or URL..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
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
              Select all {searchQuery && "matching"}
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

      {sources && sources.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No sources found. Start by crawling some documentation.
        </div>
      )}

      {filteredSources.length === 0 && sources && sources.length > 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No sources match your search.
        </div>
      )}

      {filteredSources.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSources.map((source) => (
            <div
              key={source.id}
              className={`relative bg-secondary/50 rounded-lg p-6 hover:bg-secondary transition-colors group ${
                selectedSources.has(source.id) ? "ring-2 ring-primary" : ""
              }`}
            >
              <div
                className="absolute top-4 left-4 z-10 cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleSelectSource(source.id);
                }}
              >
                <div
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                    selectedSources.has(source.id)
                      ? "bg-primary border-primary"
                      : "border-input bg-background hover:border-primary"
                  }`}
                >
                  {selectedSources.has(source.id) && (
                    <Check className="h-3 w-3 text-primary-foreground" />
                  )}
                </div>
              </div>

              <div className="flex items-start justify-between mb-4">
                <Database className="h-8 w-8 text-muted-foreground ml-8" />
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {new Date(source.created_at).toLocaleDateString()}
                  </span>
                  <button
                    onClick={(e) => handleRecrawlClick(e, source)}
                    className="p-1 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Recrawl source"
                    disabled={recrawlMutation.isPending}
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <button
                    onClick={(e) => handleDeleteClick(e, source)}
                    className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete source"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="mb-4">
                <EditableSourceName
                  id={source.id}
                  name={source.name}
                  onUpdate={handleUpdateSourceName}
                  className="text-lg font-medium"
                />
                <div className="text-xs text-muted-foreground mt-1 truncate">
                  {source.base_url}
                </div>
              </div>

              <div className="flex items-center justify-between">
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
                <Link 
                  to={`/sources/${source.id}`} 
                  className="text-sm text-primary hover:text-primary/80 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  View Details →
                </Link>
              </div>
            </div>
          ))}
        </div>
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
  );
}