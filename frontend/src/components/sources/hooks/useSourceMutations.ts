import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../../lib/api'
import { useToast } from '../../../hooks/useToast'

export const useSourceMutations = () => {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => api.deleteSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
    onError: (error) => {
      console.error("Failed to delete source:", error)
      toast.error(
        "Failed to delete source: " +
          (error instanceof Error ? error.message : "Unknown error")
      )
    },
  })

  const bulkDeleteMutation = useMutation({
    mutationFn: (sourceIds: string[]) => api.deleteBulkSources(sourceIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
    onError: (error) => {
      console.error("Failed to delete sources:", error)
      toast.error(
        "Failed to delete sources: " +
          (error instanceof Error ? error.message : "Unknown error")
      )
    },
  })

  const filteredDeleteMutation = useMutation({
    mutationFn: (params: {
      min_snippets?: number
      max_snippets?: number
      query?: string
    }) => api.deleteFilteredSources(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
    onError: (error) => {
      console.error("Failed to delete filtered sources:", error)
      toast.error(
        "Failed to delete filtered sources: " +
          (error instanceof Error ? error.message : "Unknown error")
      )
    },
  })

  const updateSourceNameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.updateSourceName(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
    onError: (error) => {
      console.error("Failed to update source name:", error)
      throw error
    },
  })

  const recrawlMutation = useMutation({
    mutationFn: ({ sourceId, ignoreHash }: { sourceId: string; ignoreHash: boolean }) => 
      api.recrawlSource(sourceId, ignoreHash),
    onSuccess: (data) => {
      navigate(`/crawl/${data.id}`)
    },
    onError: (error) => {
      console.error("Failed to recrawl source:", error)
      toast.error(
        "Failed to recrawl source: " +
          (error instanceof Error ? error.message : "Unknown error")
      )
    },
  })

  return {
    deleteMutation,
    bulkDeleteMutation,
    filteredDeleteMutation,
    updateSourceNameMutation,
    recrawlMutation
  }
}