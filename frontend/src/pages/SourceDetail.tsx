import {
  useParams,
  Link,
} from "react-router-dom";
import { useSourceDetail } from "../hooks/useSourceDetail";
import {
  ArrowLeft,
  Database,
  Search,
  X,
  Trash2,
} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SourceOverview } from "../components/SourceOverview";
import { SourceDocumentsTab } from "../components/SourceDocumentsTab";
import { SourceSnippetsTab } from "../components/SourceSnippetsTab";
import { SourceActions } from "../components/SourceActions";
import { EditableSourceName } from "../components/EditableSourceName";
import { PaginationControls } from "../components/PaginationControls";

export default function SourceDetail() {
  const { id } = useParams<{ id: string }>();
  const state = useSourceDetail(id || '');
  
  if (!id) {
    return <div>Error: Missing source ID</div>;
  }
  
  const handleConfirmDelete = () => {
    state.deleteMutation.mutate();
  };
  
  const handleUpdateSourceName = async (_sourceId: string, newName: string) => {
    await state.updateSourceNameMutation.mutateAsync({ name: newName });
  };

  if (state.sourceLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading source details...</div>
      </div>
    );
  }

  if (state.sourceError || !state.source) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive mb-2">Source Not Found</h1>
          <p className="text-muted-foreground mb-4">
            This source may have been deleted or never existed.
          </p>
          <a
            href="/sources"
            className="inline-flex items-center text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to sources
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Fixed header section */}
      <div className="space-y-4 pb-4">
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
                  id={state.source.id}
                  name={state.source.name}
                  onUpdate={handleUpdateSourceName}
                  className="text-2xl font-bold"
                />
                <a
                  href={state.source.base_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  {state.source.base_url}
                </a>
              </div>
            </div>
            <SourceActions
              source={state.source}
              deleteModalOpen={state.deleteModalOpen}
              deleteMatchesModalOpen={state.deleteMatchesModalOpen}
              deleteMutation={state.deleteMutation}
              deleteMatchesMutation={state.deleteMatchesMutation}
              setDeleteModalOpen={state.setDeleteModalOpen}
              setDeleteMatchesModalOpen={state.setDeleteMatchesModalOpen}
              handleConfirmDelete={handleConfirmDelete}
            />
          </div>

          {/* Tabs */}
          <div className="border-b border-border">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => state.handleTabChange("overview")}
                className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                  state.activeTab === "overview"
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => state.handleTabChange("documents")}
                className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                  state.activeTab === "documents"
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Documents ({state.source.documents_count})
              </button>
              <button
                onClick={() => state.handleTabChange("snippets")}
                className={`py-2 px-1 border-b-2 font-medium text-sm cursor-pointer ${
                  state.activeTab === "snippets"
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                Code Snippets ({state.source.snippets_count})
              </button>
            </nav>
          </div>
        </div>
        
        {/* Search/Filter controls for snippets tab */}
        {state.activeTab === "snippets" && (
          <div className="mt-4 px-6">
            <div className="flex items-center justify-between mb-4 gap-2">
              <div className="flex gap-3 flex-1 min-w-0">
                <div className="flex-1 relative min-w-[300px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search code snippets..."
                    value={state.snippetsSearch}
                    onChange={(e) => state.setSnippetsSearch(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  {state.snippetsSearch && (
                    <>
                      <span className="absolute right-12 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                        {state.snippets && state.snippets.total > 0 ? `(${state.snippets.total} matches)` : '(0 matches)'}
                      </span>
                      <button
                        onClick={() => state.setSnippetsSearch("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </>
                  )}
                </div>

                {state.languages && state.languages.languages.length > 0 && (
                  <Select value={state.selectedLanguage || "all"} onValueChange={(value) => {
                    state.setSelectedLanguage(value === "all" ? "" : value);
                    state.setSnippetsPage(1);
                  }}>
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
              
              <button
                onClick={() => state.setDeleteMatchesModalOpen(true)}
                disabled={state.snippetsLoading || !state.snippets || state.snippets.total === 0 || !state.debouncedSnippetsSearch}
                className="flex items-center gap-2 px-4 py-2 text-sm bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/80 disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px] justify-center h-10 cursor-pointer"
              >
                <Trash2 className="h-4 w-4" />
                Delete Matches
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Scrollable tab content */}
      <div className="flex-1 min-h-0 overflow-auto pb-4">
        <div className="px-6">
          {state.activeTab === "overview" && (
            <SourceOverview source={state.source} />
          )}

          {state.activeTab === "documents" && (
            <SourceDocumentsTab
              documents={state.documents}
              docsLoading={state.docsLoading}
            />
          )}

          {state.activeTab === "snippets" && (
            <SourceSnippetsTab
              snippets={state.snippets}
              languages={state.languages}
              snippetsLoading={state.snippetsLoading}
              snippetsPage={state.snippetsPage}
              selectedLanguage={state.selectedLanguage}
              snippetsSearch={state.snippetsSearch}
              debouncedSnippetsSearch={state.debouncedSnippetsSearch}
              snippetsPerPage={state.snippetsPerPage}
              snippetsTotalPages={state.snippetsTotalPages}
              setSnippetsPage={state.setSnippetsPage}
              setSelectedLanguage={state.setSelectedLanguage}
              setSnippetsSearch={state.setSnippetsSearch}
              setDeleteMatchesModalOpen={state.setDeleteMatchesModalOpen}
              hideSearch={true}
            />
          )}
        </div>
      </div>

      {/* Pagination Controls - Always visible at bottom */}
      {state.activeTab === "documents" && state.documents && (
        <div className="pt-4 border-t border-border">
          <PaginationControls
            currentPage={state.docsPage}
            totalPages={state.docsTotalPages}
            onPageChange={state.setDocsPage}
            totalItems={state.documents.total}
            itemsPerPage={state.docsPerPage}
            currentItemsCount={state.documents.documents.length}
          />
        </div>
      )}
      
      {state.activeTab === "snippets" && state.snippets && (
        <div className="pt-4 border-t border-border">
          <PaginationControls
            currentPage={state.snippetsPage}
            totalPages={state.snippetsTotalPages}
            onPageChange={state.setSnippetsPage}
            totalItems={state.snippets.total}
            itemsPerPage={state.snippetsPerPage}
            currentItemsCount={state.snippets.snippets.length}
          />
        </div>
      )}
    </div>
  );
}