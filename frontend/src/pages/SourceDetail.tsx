import { useState, useMemo, useEffect } from "react";
import {
  useParams,
  Link,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import {
  ArrowLeft,
  Database,
  FileText,
  Code,
  Calendar,
  Search,
  Trash2,
  X,
  ChevronDown,
  Wand2,
} from "lucide-react";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { DocumentList } from "../components/DocumentList";
import { SnippetList } from "../components/SnippetList";
import { PaginationControls } from "../components/PaginationControls";
import { useDebounce } from "../hooks/useDebounce";
import { EditableSourceName } from "../components/EditableSourceName";
import { FormatSourceDialog } from "../components/FormatSourceDialog";
import { Spinner } from "../components/Spinner";

type TabType = "overview" | "documents" | "snippets";

export default function SourceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [formatDialogOpen, setFormatDialogOpen] = useState(false);
  const [formatPreview, setFormatPreview] = useState<{
    source_id: string
    source_name: string
    total_snippets: number
    changed_snippets: number
    saved_snippets: number
    preview: Array<{
      snippet_id: number
      title: string
      language: string
      original_preview: string
      formatted_preview: string
    }>
  } | null>(null);

  // Initialize tab from URL or default to 'overview'
  const tabFromUrl = searchParams.get("tab") as TabType | null;
  const [activeTab, setActiveTab] = useState<TabType>(
    tabFromUrl && ["overview", "documents", "snippets"].includes(tabFromUrl)
      ? tabFromUrl
      : "overview"
  );

  // Update URL when tab changes
  const handleTabChange = (newTab: TabType) => {
    setActiveTab(newTab);
    if (newTab === "overview") {
      searchParams.delete("tab");
    } else {
      searchParams.set("tab", newTab);
    }
    setSearchParams(searchParams);
  };

  // Documents pagination
  const [docsPage, setDocsPage] = useState(1);
  const docsPerPage = 20;

  // Snippets pagination and filters
  const [snippetsPage, setSnippetsPage] = useState(1);
  const [snippetsSearch, setSnippetsSearch] = useState(searchParams.get("search") || "");
  const [selectedLanguage, setSelectedLanguage] = useState(searchParams.get("language") || "");
  const snippetsPerPage = 20;

  // Debounce the search query to avoid too many API calls
  const debouncedSnippetsSearch = useDebounce(snippetsSearch, 300);

  // Reset page when debounced search changes
  useEffect(() => {
    if (debouncedSnippetsSearch !== undefined) {
      setSnippetsPage(1);
    }
  }, [debouncedSnippetsSearch]);

  // Update URL parameters when search values change
  useEffect(() => {
    if (activeTab === 'snippets') {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        
        // Update search parameter
        if (debouncedSnippetsSearch) {
          newParams.set('search', debouncedSnippetsSearch);
        } else {
          newParams.delete('search');
        }
        
        // Update language parameter
        if (selectedLanguage) {
          newParams.set('language', selectedLanguage);
        } else {
          newParams.delete('language');
        }
        
        // Always set the tab parameter for snippets tab
        newParams.set('tab', 'snippets');
        
        return newParams;
      }, { replace: true });
    }
  }, [debouncedSnippetsSearch, selectedLanguage, activeTab, setSearchParams]);

  const {
    data: source,
    isLoading: sourceLoading,
    error: sourceError,
  } = useQuery({
    queryKey: ["source", id],
    queryFn: () => api.getSource(id!),
    enabled: !!id,
  });

  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ["source-documents", id, docsPage],
    queryFn: () =>
      api.getSourceDocuments(id!, {
        limit: docsPerPage,
        offset: (docsPage - 1) * docsPerPage,
      }),
    enabled: !!id && activeTab === "documents",
  });

  const { data: snippets, isLoading: snippetsLoading } = useQuery({
    queryKey: [
      "source-snippets",
      id,
      snippetsPage,
      debouncedSnippetsSearch,
      selectedLanguage,
    ],
    queryFn: () =>
      api.getSourceSnippets(id!, {
        query: debouncedSnippetsSearch || undefined,
        language: selectedLanguage || undefined,
        limit: snippetsPerPage,
        offset: (snippetsPage - 1) * snippetsPerPage,
      }),
    enabled: !!id && activeTab === "snippets",
  });

  const { data: languages } = useQuery({
    queryKey: ["source-languages", id],
    queryFn: () => api.getSourceLanguages(id!),
    enabled: !!id && activeTab === "snippets",
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSource(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      navigate("/sources");
    },
    onError: (error) => {
      console.error("Failed to delete source:", error);
      alert(
        "Failed to delete source: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const updateSourceNameMutation = useMutation({
    mutationFn: ({ name }: { name: string }) =>
      api.updateSourceName(id!, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source", id] });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error) => {
      console.error("Failed to update source name:", error);
      throw error;
    },
  });

  const confirmDelete = () => {
    deleteMutation.mutate();
  };

  const handleUpdateSourceName = async (_sourceId: string, newName: string) => {
    await updateSourceNameMutation.mutateAsync({ name: newName });
  };

  const formatPreviewMutation = useMutation({
    mutationFn: () => api.formatSource(id!, false, true),
    onSuccess: (data) => {
      setFormatPreview(data);
      setFormatDialogOpen(true);
    },
    onError: (error) => {
      console.error('Failed to get format preview:', error);
      alert('Failed to get format preview');
    }
  });

  const formatSourceMutation = useMutation({
    mutationFn: () => api.formatSource(id!, true, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['source-snippets', id] });
      setFormatDialogOpen(false);
      setFormatPreview(null);
    },
    onError: (error) => {
      console.error('Failed to format source:', error);
      alert('Failed to format source');
    }
  });

  const handleFormatAll = () => {
    formatPreviewMutation.mutate();
  };

  const handleConfirmFormat = () => {
    formatSourceMutation.mutate();
  };

  const docsTotalPages = useMemo(
    () => (documents ? Math.ceil(documents.total / docsPerPage) : 0),
    [documents]
  );

  const snippetsTotalPages = useMemo(
    () => (snippets ? Math.ceil(snippets.total / snippetsPerPage) : 0),
    [snippets]
  );

  if (sourceLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading source details...</div>
      </div>
    );
  }

  if (sourceError || !source) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Error loading source</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-4">
        <Link
          to="/sources"
          className="flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to sources
        </Link>
      </div>

      <div className="bg-secondary/50 rounded-lg p-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <Database className="h-8 w-8 text-muted-foreground" />
            <div>
              <EditableSourceName
                id={source.id}
                name={source.name}
                onUpdate={handleUpdateSourceName}
                className="text-2xl font-bold"
              />
              <a
                href={source.base_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                {source.base_url}
              </a>
            </div>
          </div>
          <button
            onClick={() => setDeleteModalOpen(true)}
            className="flex items-center px-3 py-1.5 text-sm text-destructive border border-destructive rounded-md hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4 mr-1.5" />
            Delete Source
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-border">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => handleTabChange("overview")}
              className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                activeTab === "overview"
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => handleTabChange("documents")}
              className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                activeTab === "documents"
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Documents ({source.documents_count})
            </button>
            <button
              onClick={() => handleTabChange("snippets")}
              className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                activeTab === "snippets"
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Code Snippets ({source.snippets_count})
            </button>
          </nav>
        </div>

        {/* Tab Content */}
        <div className="pt-6">
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-background rounded-md p-4">
                  <div className="flex items-center text-muted-foreground mb-1">
                    <FileText className="h-4 w-4 mr-2" />
                    <span className="text-sm">Documents</span>
                  </div>
                  <p className="text-2xl font-semibold">
                    {source.documents_count}
                  </p>
                </div>

                <div className="bg-background rounded-md p-4">
                  <div className="flex items-center text-muted-foreground mb-1">
                    <Code className="h-4 w-4 mr-2" />
                    <span className="text-sm">Code Snippets</span>
                  </div>
                  <p className="text-2xl font-semibold">
                    {source.snippets_count}
                  </p>
                </div>

                <div className="bg-background rounded-md p-4">
                  <div className="flex items-center text-muted-foreground mb-1">
                    <Calendar className="h-4 w-4 mr-2" />
                    <span className="text-sm">Created</span>
                  </div>
                  <p className="text-sm font-medium">
                    {new Date(source.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <Link
                to={`/search?source=${encodeURIComponent(source.name)}`}
                className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                <Search className="h-4 w-4 mr-2" />
                Search all snippets from this source
              </Link>
            </div>
          )}

          {activeTab === "documents" && (
            <div className="space-y-4">
              {docsLoading ? (
                <div className="text-center py-8 text-muted-foreground">
                  Loading documents...
                </div>
              ) : documents ? (
                <>
                  <DocumentList documents={documents.documents} />
                  {docsTotalPages > 1 && (
                    <PaginationControls
                      currentPage={docsPage}
                      totalPages={docsTotalPages}
                      onPageChange={setDocsPage}
                      totalItems={documents.total}
                      itemsPerPage={docsPerPage}
                      currentItemsCount={documents.documents.length}
                    />
                  )}
                </>
              ) : null}
            </div>
          )}

          {activeTab === "snippets" && (
            <div className="space-y-4">
              {/* Search and Filter Bar */}
              <div className="flex items-center justify-between mb-4 gap-2">
                <div className="flex gap-3 flex-1">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search code snippets..."
                    value={snippetsSearch}
                    onChange={(e) => {
                      setSnippetsSearch(e.target.value);
                    }}
                    className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  {snippetsSearch && (
                    <button
                      onClick={() => {
                        setSnippetsSearch("");
                      }}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>

                {languages && languages.languages.length > 0 && (
                  <div className="relative min-w-48">
                    <select
                      value={selectedLanguage}
                      onChange={(e) => {
                        setSelectedLanguage(e.target.value);
                        setSnippetsPage(1);
                      }}
                      className="appearance-none pl-4 pr-10 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer bg-right"
                    >
                      <option value="">All Languages</option>
                      {languages.languages.map((lang) => (
                        <option key={lang.name} value={lang.name}>
                          {lang.name} ({lang.count})
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                  </div>
                )}
                </div>
                
                <button
                  onClick={handleFormatAll}
                  disabled={formatPreviewMutation.isPending || snippetsLoading || !snippets || snippets.total === 0}
                  className="flex items-center gap-2 px-4 py-2 text-sm bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px] justify-center h-10 cursor-pointer"
                >
                  {formatPreviewMutation.isPending ? (
                    <>
                      <Spinner size="sm" className="text-secondary-foreground" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-4 w-4" />
                      Format All
                    </>
                  )}
                </button>
              </div>

              {/* Snippets List */}
              {snippetsLoading ? (
                <div className="text-center py-8 text-muted-foreground">
                  Searching snippets...
                </div>
              ) : snippets ? (
                <>
                  <SnippetList
                    snippets={snippets.snippets}
                    showSource={false}
                  />
                  {snippetsTotalPages > 1 && (
                    <PaginationControls
                      currentPage={snippetsPage}
                      totalPages={snippetsTotalPages}
                      onPageChange={setSnippetsPage}
                      totalItems={snippets.total}
                      itemsPerPage={snippetsPerPage}
                      currentItemsCount={snippets.snippets.length}
                    />
                  )}
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <ConfirmationDialog
        isOpen={deleteModalOpen}
        title="Confirm Delete"
        message={`Are you sure you want to delete the source "${source.name}"? This will permanently remove all ${source.documents_count} documents and ${source.snippets_count} code snippets.`}
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteModalOpen(false)}
      />

      {formatPreview && (
        <FormatSourceDialog
          isOpen={formatDialogOpen}
          sourceName={source.name}
          totalSnippets={formatPreview.total_snippets}
          changedSnippets={formatPreview.changed_snippets}
          preview={formatPreview.preview}
          isFormatting={formatSourceMutation.isPending}
          onConfirm={handleConfirmFormat}
          onCancel={() => {
            setFormatDialogOpen(false)
            setFormatPreview(null)
          }}
        />
      )}
    </div>
  );
}
