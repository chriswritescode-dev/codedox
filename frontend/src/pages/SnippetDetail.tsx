import { useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { ArrowLeft, Code, Link as LinkIcon, Copy, Check } from 'lucide-react'
import { useState } from 'react'

export default function SnippetDetail() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const [copied, setCopied] = useState(false)
  
  const { data: snippet, isLoading, error } = useQuery({
    queryKey: ['snippet', id],
    queryFn: () => api.getSnippet(id!),
    enabled: !!id,
  })

  

  useEffect(() => {
    if (snippet && typeof (window as any).hljs !== 'undefined') {
      const codeElement = document.querySelector('.code-content')
      if (codeElement) {
        (window as any).hljs.highlightElement(codeElement)
      }
    }
  }, [snippet])

  const handleCopy = async () => {
    if (snippet?.code) {
      await navigator.clipboard.writeText(snippet.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading snippet...</div>
      </div>
    )
  }

  if (error || !snippet) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Error loading snippet</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-4">
        <Link
          to={location.state?.from || "/search"}
          className="flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Link>
      </div>

      <div className="bg-secondary/50 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Code className="h-6 w-6" />
              {snippet.document_title}
            </h1>
            {snippet.description && (
              <p className="text-muted-foreground mt-2">
                {snippet.description}
              </p>
            )}
          </div>
          <span className="px-3 py-1 bg-primary/10 text-primary rounded-md text-sm font-medium">
            {snippet.language}
          </span>
        </div>

        <div className="space-y-4 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <LinkIcon className="h-4 w-4" />
            <a
              href={snippet.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary hover:underline truncate"
            >
              {snippet.source_url}
            </a>
          </div>
        </div>
      </div>

      <div className="bg-secondary/50 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-secondary border-b border-border">
          <span className="text-sm font-medium">Code</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-background rounded hover:bg-primary/10 transition-colors"
          >
            {copied ? (
              <Check className="h-3 w-3" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="p-4 overflow-x-auto">
          <code className={`code-content language-${snippet.language} block`}>
            {snippet.code}
          </code>
        </pre>
      </div>
    </div>
  );
}