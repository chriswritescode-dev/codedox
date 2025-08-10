import { useNavigate, useParams } from "react-router-dom";
import { DocumentList } from "./DocumentList";
import { PaginationControls } from "./PaginationControls";
import { Document } from "../lib/api";

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
  const navigate = useNavigate();
  const { id: sourceId } = useParams<{ id: string }>();
  
  const handleDocumentClick = (doc: Document) => {
    if (sourceId) {
      navigate(`/sources/${sourceId}/documents/${doc.id}`);
    }
  };
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
      <DocumentList documents={documents.documents} onDocumentClick={handleDocumentClick} />
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