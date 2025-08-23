import { useState } from "react";
import { FileText, Code, ExternalLink, Clock, Eye, Upload } from "lucide-react";
import { Document } from '../lib/api'
import { FullPageModal } from "./FullPageModal";

interface DocumentListProps {
  documents: Document[]
  onDocumentClick?: (doc: Document) => void
}

export function DocumentList({ documents, onDocumentClick }: DocumentListProps) {
  const [selectedDocUrl, setSelectedDocUrl] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleViewMarkdown = (e: React.MouseEvent, url: string) => {
    e.stopPropagation();
    setSelectedDocUrl(url);
    setIsModalOpen(true);
  };

  const isUploadedDoc = (url: string) => {
    return url.startsWith('upload://') || url.startsWith('file://');
  };

  const getDisplayName = (url: string) => {
    if (isUploadedDoc(url)) {
      // Extract filename from upload:// or file:// URL
      const parts = url.replace(/^(upload|file):\/\//, '').split('/');
      return parts[parts.length - 1] || 'Uploaded Document';
    }
    return url;
  };
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No documents found.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="bg-secondary/50 rounded-lg p-4 hover:bg-secondary transition-colors"
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-start gap-3">
              {isUploadedDoc(doc.url) ? (
                <Upload className="h-5 w-5 text-muted-foreground mt-0.5" />
              ) : (
                <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
              )}
              <div className="flex-1">
                <h3 className="font-medium text-foreground mb-1">
                  {doc.title}
                </h3>
                {isUploadedDoc(doc.url) ? (
                  <div className="text-sm text-muted-foreground inline-flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    <span title="Uploaded markdown document">{getDisplayName(doc.url)}</span>
                  </div>
                ) : (
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:text-primary/80 hover:underline inline-flex items-center gap-1 transition-colors"
                    title="Open website in new tab"
                  >
                    {doc.url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <button
                onClick={(e) => handleViewMarkdown(e, doc.url)}
                className={`flex items-center gap-1 px-2 py-1 rounded hover:bg-accent hover:text-accent-foreground transition-colors cursor-pointer ${
                  isUploadedDoc(doc.url) ? 'bg-primary/10 text-primary font-medium' : ''
                }`}
                title={isUploadedDoc(doc.url) ? "View uploaded document content" : "View markdown content"}
              >
                <Eye className="h-4 w-4" />
                <span>{isUploadedDoc(doc.url) ? 'View Document' : 'View Markdown'}</span>
              </button>
              <div className="flex flex-col items-center">
                <div className="flex items-center gap-1">
                  <Code className="h-4 w-4" />
                  <span>{doc.snippets_count} snippets</span>
                </div>
                <button
                  onClick={() => onDocumentClick?.(doc)}
                  className="text-sm text-muted-foreground hover:text-foreground hover:underline inline-flex items-center gap-1 transition-colors ml-2 cursor-pointer"
                  title="View snippets for this source"
                >
                  (View Snippets)
                </button>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                <span>{new Date(doc.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
            <span>Depth: {doc.crawl_depth}</span>
          </div>
        </div>
      ))}

      {selectedDocUrl && (
        <FullPageModal
          url={selectedDocUrl}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedDocUrl(null);
          }}
        />
      )}
    </div>
  );
}
