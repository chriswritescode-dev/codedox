import { FileText, Code, ExternalLink, Clock } from 'lucide-react'
import { Document } from '../lib/api'

interface DocumentListProps {
  documents: Document[]
  onDocumentClick?: (doc: Document) => void
}

export function DocumentList({ documents, onDocumentClick }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No documents found.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="bg-secondary/50 rounded-lg p-4 hover:bg-secondary transition-colors cursor-pointer"
          onClick={() => onDocumentClick?.(doc)}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-start gap-3">
              <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div className="flex-1">
                <h3 className="font-medium text-foreground mb-1">
                  {doc.title}
                </h3>
                <a
                  href={doc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline inline-flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  {doc.url}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <Code className="h-4 w-4" />
                <span>{doc.snippets_count} snippets</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                <span>{new Date(doc.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
            <span>Depth: {doc.crawl_depth}</span>
            <span>•</span>
            <span className={`capitalize ${
              doc.enrichment_status === 'completed' ? 'text-green-600' :
              doc.enrichment_status === 'failed' ? 'text-red-600' :
              doc.enrichment_status === 'processing' ? 'text-yellow-600' :
              'text-muted-foreground'
            }`}>
              {doc.enrichment_status}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}