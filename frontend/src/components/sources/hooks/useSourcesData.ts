import { useQuery } from '@tanstack/react-query'
import { api } from '../../../lib/api'

interface UseSourcesDataProps {
  currentPage: number
  itemsPerPage: number
  debouncedSearchQuery: string
  snippetFilter: string
}

export const useSourcesData = ({
  currentPage,
  itemsPerPage,
  debouncedSearchQuery,
  snippetFilter
}: UseSourcesDataProps) => {
  const getSnippetBounds = () => {
    switch(snippetFilter) {
      case '0': return { min: 0, max: 0 }
      case 'has-snippets': return { min: 1, max: undefined }
      default: return { min: undefined, max: undefined }
    }
  }

  return useQuery({
    queryKey: ["sources", currentPage, itemsPerPage, debouncedSearchQuery, snippetFilter],
    queryFn: () => {
      const offset = (currentPage - 1) * itemsPerPage
      const bounds = getSnippetBounds()
      
      if (debouncedSearchQuery || snippetFilter !== 'all') {
        return api.searchSources({
          query: debouncedSearchQuery || undefined,
          min_snippets: bounds.min,
          max_snippets: bounds.max,
          limit: itemsPerPage,
          offset
        })
      }
      
      return api.getSources({ limit: itemsPerPage, offset })
    },
  })
}