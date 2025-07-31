import { useState } from "react";
import {
  useParams,
  Link,
} from "react-router-dom";
import { useSourceDetail } from "../hooks/useSourceDetail";
import {
  ArrowLeft,
  Database,
} from "lucide-react";
import { SourceOverview } from "../components/SourceOverview";
import { SourceDocumentsTab } from "../components/SourceDocumentsTab";
import { SourceSnippetsTab } from "../components/SourceSnippetsTab";
import { SourceActions } from "../components/SourceActions";
import { EditableSourceName } from "../components/EditableSourceName";

export default function SourceDetail() {
  const { id } = useParams<{ id: string }>();
  
  if (!id) {
    return <div>Error: Missing source ID</div>;
  }
  
  const state = useSourceDetail(id);
  
  const handleConfirmDelete = () => {
    state.deleteMutation.mutate();
  };
  
  const handleUpdateSourceName = async (sourceId: string, newName: string) => {
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
            formatDialogOpen={state.formatDialogOpen}
            formatPreview={state.formatPreview}
            deleteMutation={state.deleteMutation}
            deleteMatchesMutation={state.deleteMatchesMutation}
            updateSourceNameMutation={state.updateSourceNameMutation}
            formatPreviewMutation={state.formatPreviewMutation}
            formatSourceMutation={state.formatSourceMutation}
            handleFormatAll={() => state.formatPreviewMutation.mutate()}
            handleConfirmFormat={() => state.formatSourceMutation.mutate()}
            setDeleteModalOpen={state.setDeleteModalOpen}
            setDeleteMatchesModalOpen={state.setDeleteMatchesModalOpen}
            setFormatDialogOpen={state.setFormatDialogOpen}
            setFormatPreview={state.setFormatPreview}
            handleUpdateSourceName={handleUpdateSourceName}
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

        {/* Tab Content */}
        <div className="pt-6">
          {state.activeTab === "overview" && (
            <SourceOverview source={state.source} />
          )}

          {state.activeTab === "documents" && (
            <SourceDocumentsTab
              documents={state.documents}
              docsLoading={state.docsLoading}
              docsPage={state.docsPage}
              docsPerPage={state.docsPerPage}
              docsTotalPages={state.docsTotalPages}
              setDocsPage={state.setDocsPage}
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
              formatPreviewMutation={state.formatPreviewMutation}
              formatSourceMutation={state.formatSourceMutation}
              handleConfirmFormat={() => state.formatSourceMutation.mutate()}
              setDeleteMatchesModalOpen={state.setDeleteMatchesModalOpen}
              deleteMatchesMutation={state.deleteMatchesMutation}
            />
          )}
        </div>
      </div>
    </div>
  );
}