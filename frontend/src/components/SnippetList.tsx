import { Link } from 'react-router-dom'
import { FileText, ExternalLink } from 'lucide-react'
import { CodeSnippet } from '../lib/api'

interface SnippetListProps {
  snippets: CodeSnippet[]
  showSource?: boolean
}

export function SnippetList({ snippets, showSource = true }: SnippetListProps) {
  if (snippets.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground ">
        No code snippets found.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {snippets.map((snippet) => (
        <Link
          key={snippet.id}
          to={`/snippets/${snippet.id}`}
          state={{ from: window.location.pathname + window.location.search }}
          className="block bg-secondary/50 rounded-lg p-4 hover:bg-secondary transition-colors"
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1">
              <h3 className="font-medium text-foreground mb-1">
                {snippet.title || snippet.document_title}
              </h3>
              {showSource && snippet.source_url && (
                <div className="flex items-center gap-1 text-sm text-muted-foreground">
                  <FileText className="h-3 w-3" />
                  <span className="truncate max-w-md">{snippet.source_url}</span>
                  <ExternalLink className="h-3 w-3" />
                </div>
              )}
            </div>
            <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded">
              {snippet.language}
            </span>
          </div>

          {snippet.description && (
            <p className="text-sm text-muted-foreground mb-3">
              {snippet.description} f
            </p>
          )}

          <div className="relative">
            <pre className="text-xs bg-background p-3 rounded truncate  max-h-20">
              <code>{snippet.code.slice(0, 300)}{snippet.code.length > 300 ? '...' : ''}</code>
            </pre>
            {snippet.code.length > 300 && (
              <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-background to-transparent pointer-events-none" />
            )}
          </div>

        
        </Link>
      ))}
    </div>
  )
}
