import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Search as SearchIcon } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [sourceName, setSourceName] = useState(searchParams.get('source') || '')
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [language, setLanguage] = useState(searchParams.get('lang') || '')

  // Update URL when search parameters change
  useEffect(() => {
    const params = new URLSearchParams()
    if (sourceName) params.set('source', sourceName)
    if (query) params.set('q', query)
    if (language) params.set('lang', language)
    setSearchParams(params, { replace: true })
  }, [sourceName, query, language, setSearchParams])

  const { data: results, isLoading } = useQuery({
    queryKey: ['search', sourceName, query, language],
    queryFn: () => api.search({ source_name: sourceName, query, language, limit: 20 }),
    enabled: !!(sourceName || query || language),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    // The query will automatically run due to the enabled condition
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Search Code Snippets</h1>
        <p className="text-muted-foreground mt-2">
          Search through extracted code snippets by source, content, or language
        </p>
      </div>

      <form onSubmit={handleSearch} className="space-y-4">
        <div>
          <label htmlFor="query" className="block text-sm font-medium mb-2">
            Search Query
          </label>
          <input
            type="text"
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., authentication, useState"
            className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label htmlFor="source" className="block text-sm font-medium mb-2">
            Source Name
          </label>
          <input
            type="text"
            id="source"
            value={sourceName}
            onChange={(e) => setSourceName(e.target.value)}
            placeholder="e.g., Next.js"
            className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label htmlFor="language" className="block text-sm font-medium mb-2">
            Language
          </label>
          <input
            type="text"
            id="language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            placeholder="e.g., javascript, python"
            className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        <button
          type="submit"
          disabled={!sourceName && !query && !language}
          className="flex items-center justify-center w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <SearchIcon className="h-4 w-4 mr-2" />
          Search
        </button>
      </form>

      {/* Results */}
      {isLoading && (
        <div className="text-center py-8 text-muted-foreground">
          Searching...
        </div>
      )}

      {results && results.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No results found
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">
            {results.length} result{results.length !== 1 ? "s" : ""} found
          </h2>

          {results.map((result) => (
            <Link
              key={result.snippet.id}
              to={`/snippets/${result.snippet.id}`}
              state={{ from: window.location.pathname + window.location.search }}
              className="block bg-secondary/50 rounded-lg p-4 hover:bg-secondary transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium">{result.snippet.document_title}</h3>
                <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded">
                  {result.snippet.language}
                </span>
              </div>

              {result.snippet.description && (
                <p className="text-sm text-muted-foreground mb-2">
                  {result.snippet.description}
                </p>
              )}

              <pre className="text-xs bg-background p-2 rounded overflow-x-auto">
                <code>{result.snippet.code.slice(0, 200)}...</code>
              </pre>

              <div className="mt-2 text-xs text-muted-foreground">
                {result.snippet.source_url}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}