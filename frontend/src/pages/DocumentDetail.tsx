import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { 
  ArrowLeft, 
  FileText, 
  Code, 
  ExternalLink, 
  Search,
  X,
  Filter
} from 'lucide-react'
import { SnippetList } from '../components/SnippetList'
import { PaginationControls } from '../components/PaginationControls'
import { useDebounce } from '../hooks/useDebounce'

export default function DocumentDetail() {
  const { sourceId, documentId } = useParams<{ sourceId: string; documentId: string }>()
  
  const [currentPage, setCurrentPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState('')
  const itemsPerPage = 10
  
  const debouncedSearchQuery = useDebounce(searchQuery, 300)
  
  const { 
    data, 
    isLoading, 
    error 
  } = useQuery({
    queryKey: ['document-snippets', documentId, currentPage, debouncedSearchQuery, selectedLanguage],
    queryFn: () => api.getDocumentSnippets(
      parseInt(documentId!),
      {
        query: debouncedSearchQuery || undefined,
        language: selectedLanguage || undefined,
        limit: itemsPerPage,
        offset: (currentPage - 1) * itemsPerPage
      }
    ),
    enabled: !!documentId,
  })
  
  // Get unique languages from snippets
  const languages = useMemo(() => {
    if (!data?.snippets) return []
    const langSet = new Set(data.snippets.map(s => s.language).filter(Boolean))
    return Array.from(langSet).sort()
  }, [data?.snippets])
  
  const totalPages = useMemo(
    () => (data ? Math.ceil(data.total / itemsPerPage) : 0),
    [data]
  )
  
  // Reset page when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearchQuery, selectedLanguage])
  
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
  }, [])
  
  const handleLanguageChange = useCallback((value: string) => {
    setSelectedLanguage(value)
  }, [])
  
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page)
  }, [])
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading document snippets...</div>
      </div>
    )
  }
  
  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive mb-2">Document Not Found</h1>
          <p className="text-muted-foreground mb-4">
            This document may have been deleted or never existed.
          </p>
          <Link
            to={`/sources/${sourceId}`}
            className="inline-flex items-center text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to source
          </Link>
        </div>
      </div>
    )
  }
  
  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Fixed header section */}
      <div className="space-y-6 pb-4">
        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-2 text-sm">
          <Link
            to="/sources"
            className="text-muted-foreground hover:text-foreground"
          >
            Sources
          </Link>
          <span className="text-muted-foreground">/</span>
          {data.source && (
            <>
              <Link
                to={`/sources/${data.source.id}`}
                className="text-muted-foreground hover:text-foreground"
              >
                {data.source.name}
              </Link>
              <span className="text-muted-foreground">/</span>
            </>
          )}
          <span className="text-foreground">Document</span>
        </div>
        
        {/* Document header */}
        <div className="bg-secondary/50 rounded-lg p-6">
          <div className="flex items-start gap-3 mb-4">
            <FileText className="h-8 w-8 text-muted-foreground mt-1" />
            <div className="flex-1">
              <h1 className="text-2xl font-bold mb-2">
                {data.document.title}
              </h1>
              <a
                href={data.document.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline inline-flex items-center gap-1"
              >
                {data.document.url}
                <ExternalLink className="h-3 w-3" />
              </a>
              <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                <span>Depth: {data.document.crawl_depth}</span>
                <span>•</span>
                <span>{new Date(data.document.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          
          {/* Stats */}
          <div className="flex items-center gap-6 pt-4 border-t border-border">
            <div className="flex items-center gap-4">
              <Code className="h-5 w-5 text-muted-foreground" />
              <div className='flex items-center gap-2'>
                <div className="text-2xl font-semibold">{data.total}</div>
                <div className="text-sm text-muted-foreground">Code Snippets</div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Search and filter */}
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search snippets in this document..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {searchQuery && (
              <button
                onClick={() => handleSearchChange('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          
          {languages.length > 0 && (
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={selectedLanguage}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">All Languages</option>
                {languages.map(lang => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Scrollable content area */}
      <div className="flex-1 min-h-0 overflow-auto pb-4">
        <div className="max-w-6xl mx-auto w-full">
          {/* Snippets */}
          {data.snippets.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
            {debouncedSearchQuery || selectedLanguage 
              ? 'No snippets match your filters.'
              : 'No code snippets found in this document.'}
          </div>
        ) : (
          <>
            <SnippetList snippets={data.snippets} />
            
          </>
        )}
        </div>
      </div>

      {/* Pagination Controls - Always visible at bottom */}
      {data && (
        <div className="pt-4 border-t border-border">
          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={handlePageChange}
            totalItems={data.total}
            itemsPerPage={itemsPerPage}
            currentItemsCount={data.snippets.length}
          />
        </div>
      )}
    </div>
  )
}
