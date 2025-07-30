import { DocumentList } from "./DocumentList";
import { PaginationControls } from "./PaginationControls";

interface SourceDocumentsTabProps {
  documents: any;
  docsLoading: boolean;
  docsPage: number;
  docsPerPage: number;
  docsTotalPages: number;
  setDocsPage: (page: number) => void;
}

export function SourceDocumentsTab({
  documents,
  docsLoading,
  docsPage,
  docsPerPage,
  docsTotalPages,
  setDocsPage,
}: SourceDocumentsTabProps) {
  if (docsLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Loading documents...
      </div>
    );
  }

  if (!documents) {
    return null;
  }

  return (
    <div className="space-y-4">
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
    </div>
  );
}