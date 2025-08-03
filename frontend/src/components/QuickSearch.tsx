import React, { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Search as SearchIcon, ArrowRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useDebounce } from '../hooks/useDebounce'

export default function QuickSearch() {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  
  const debouncedQuery = useDebounce(query, 300)

  const { data: results, isLoading } = useQuery({
    queryKey: ['quickSearch', debouncedQuery],
    queryFn: () => api.search({ query: debouncedQuery, limit: 5 }),
    enabled: debouncedQuery.length > 0,
  })

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    setIsOpen(debouncedQuery.length > 0)
  }, [debouncedQuery])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query) {
      navigate(`/search?q=${encodeURIComponent(query)}`)
      setQuery('')
      setIsOpen(false)
    }
  }

  return (
    <div ref={searchRef} className="relative w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Quick search for code snippets..."
            className="w-full pl-10 pr-4 py-3 bg-secondary border border-input rounded-lg focus:outline-hidden focus:ring-2 focus:ring-primary text-base"
          />
        </div>
      </form>

      {isOpen && (
        <div className="absolute top-full mt-2 w-full bg-background border border-input rounded-lg shadow-lg z-50">
          {isLoading && (
            <div className="p-4 text-center text-muted-foreground">
              Searching...
            </div>
          )}

          {results && results.length === 0 && !isLoading && (
            <div className="p-4 text-center text-muted-foreground">
              No results found
            </div>
          )}

          {results && results.length > 0 && !isLoading && (
            <>
              <div className="max-h-96 overflow-y-auto">
                {results.map((result) => (
                  <Link
                    key={result.snippet.id}
                    to={`/snippets/${result.snippet.id}`}
                    onClick={() => {
                      setQuery('')
                      setIsOpen(false)
                    }}
                    className="block px-4 py-3 hover:bg-secondary border-b border-border last:border-b-0"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="font-medium text-sm">
                        {result.snippet.document_title}
                      </h4>
                      <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded">
                        {result.snippet.language}
                      </span>
                    </div>
                    {result.snippet.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {result.snippet.description}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
              
              <Link
                to={`/search?q=${encodeURIComponent(query)}`}
                onClick={() => {
                  setQuery('')
                  setIsOpen(false)
                }}
                className="flex items-center justify-center gap-2 p-3 text-sm text-primary hover:bg-secondary border-t border-border"
              >
                View all results
                <ArrowRight className="h-4 w-4" />
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  )
}