import { useQuery } from "@tanstack/react-query";
import { api, SourceOption } from "../lib/api";

export const useSources = (enabled: boolean) => {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["sources-for-update"],
    queryFn: async () => {
      const response = await api.getSources({ limit: 1000 });
      const sourceOptions: SourceOption[] = response.sources.map((source) => ({
        id: source.id,
        name: source.name,
        version: source.version || null,
        display_name: source.version
          ? `${source.name} (v${source.version})`
          : source.name,
        documents_count: source.documents_count,
        snippets_count: source.snippets_count,
        created_at: source.created_at,
        base_url: source.base_url,
      }));
      return sourceOptions;
    },
    enabled: enabled,
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });

  return { sources: data || [], isLoading: isLoading || isFetching };
};
