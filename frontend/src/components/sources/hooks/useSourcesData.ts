import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { api } from '../../../lib/api'
import { getSnippetBounds } from '../utils'

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
  return useQuery({
    queryKey: ["sources", currentPage, itemsPerPage, debouncedSearchQuery, snippetFilter],
    queryFn: () => {
      const offset = (currentPage - 1) * itemsPerPage
      const bounds = getSnippetBounds(snippetFilter)
      
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
    placeholderData: keepPreviousData,
  })
}