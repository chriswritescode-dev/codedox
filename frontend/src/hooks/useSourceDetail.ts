import { useState, useMemo, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, UseMutationResult } from "@tanstack/react-query";
import { api, Source, PaginatedDocuments, PaginatedSnippets, LanguageStat } from "../lib/api";
import { useDebounce } from "./useDebounce";
import { useToast } from "./useToast";

type TabType = "overview" | "documents" | "snippets";

interface SourceDetailState {
  id: string;
  activeTab: TabType;
  snippetsPage: number;
  docsPage: number;
  snippetsSearch: string;
  selectedLanguage: string;
  deleteModalOpen: boolean;
  deleteMatchesModalOpen: boolean;
  debouncedSnippetsSearch: string;
  
  // Computed values
  snippetsPerPage: number;
  docsPerPage: number;
  snippetsTotalPages: number;
  docsTotalPages: number;
  
  // Handlers
  handleTabChange: (tab: TabType) => void;
  setSnippetsPage: (page: number) => void;
  setDocsPage: (page: number) => void;
  setSnippetsSearch: (search: string) => void;
  setSelectedLanguage: (lang: string) => void;
  setDeleteModalOpen: (open: boolean) => void;
  setDeleteMatchesModalOpen: (open: boolean) => void;
  
  // Mutations
  deleteMutation: UseMutationResult<{ message: string }, Error, void, unknown>;
  deleteMatchesMutation: UseMutationResult<{ deleted_count: number; source_id: string; source_name: string }, Error, void, unknown>;
  updateSourceNameMutation: UseMutationResult<Source, Error, { name: string; version?: string }, unknown>;
  
  // Query data
  source: Source | undefined;
  documents: PaginatedDocuments | undefined;
  snippets: PaginatedSnippets | undefined;
  languages: { languages: LanguageStat[] } | undefined;
  docsLoading: boolean;
  snippetsLoading: boolean;
  sourceLoading: boolean;
  sourceError: Error | null;
}

export function useSourceDetail(id: string): SourceDetailState {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const toast = useToast();

  // Basic state
  const [snippetsPage, setSnippetsPage] = useState(1);
  const [docsPage, setDocsPage] = useState(1);
  const [snippetsSearch, setSnippetsSearch] = useState(searchParams.get("search") || "");
  const [selectedLanguage, setSelectedLanguage] = useState(searchParams.get("language") || "");
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteMatchesModalOpen, setDeleteMatchesModalOpen] = useState(false);

  // Tab management
  const tabFromUrl = searchParams.get("tab") as TabType | null;
  const [activeTab, setActiveTab] = useState<TabType>(
    tabFromUrl && ["overview", "documents", "snippets"].includes(tabFromUrl)
      ? tabFromUrl
      : "overview"
  );

  // Pagination settings
  const snippetsPerPage = 10;
  const docsPerPage = 20;

  // Debounce search query
  const debouncedSnippetsSearch = useDebounce(snippetsSearch, 300);

  // Initialize tab from URL or default to 'overview'
  const handleTabChange = (newTab: TabType) => {
    setActiveTab(newTab);
    if (newTab === "overview") {
      searchParams.delete("tab");
    } else {
      searchParams.set("tab", newTab);
    }
    setSearchParams(searchParams);
  };

  // Sync state with URL
  useEffect(() => {
    if (debouncedSnippetsSearch !== undefined) {
      setSnippetsPage(1);
    }
  }, [debouncedSnippetsSearch]);

  useEffect(() => {
    if (activeTab === 'snippets') {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        
        if (debouncedSnippetsSearch) {
          newParams.set('search', debouncedSnippetsSearch);
        } else {
          newParams.delete('search');
        }
        
        if (selectedLanguage) {
          newParams.set('language', selectedLanguage);
        } else {
          newParams.delete('language');
        }
        
        newParams.set('tab', 'snippets');
        return newParams;
      }, { replace: true });
    }
  }, [debouncedSnippetsSearch, selectedLanguage, activeTab, setSearchParams]);

  // Data queries
  const {
    data: source,
    isLoading: sourceLoading,
    error: sourceError,
  } = useQuery({
    queryKey: ["source", id],
    queryFn: () => api.getSource(id!),
    enabled: !!id,
  });

  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ["source-documents", id, docsPage],
    queryFn: () =>
      api.getSourceDocuments(id!, {
        limit: docsPerPage,
        offset: (docsPage - 1) * docsPerPage,
      }),
    enabled: !!id && activeTab === "documents",
  });

  const { data: snippets, isLoading: snippetsLoading } = useQuery({
    queryKey: [
      "source-snippets",
      id,
      snippetsPage,
      debouncedSnippetsSearch,
      selectedLanguage,
    ],
    queryFn: () =>
      api.getSourceSnippets(id!, {
        query: debouncedSnippetsSearch || undefined,
        language: selectedLanguage || undefined,
        limit: snippetsPerPage,
        offset: (snippetsPage - 1) * snippetsPerPage,
      }),
    enabled: !!id && activeTab === "snippets",
  });

  const { data: languages } = useQuery({
    queryKey: ["source-languages", id],
    queryFn: () => api.getSourceLanguages(id!),
    enabled: !!id && activeTab === "snippets",
  });

  // Mutations
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSource(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      navigate("/sources");
    },
    onError: (error) => {
      console.error("Failed to delete source:", error);
      toast.error(
        "Failed to delete source: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const deleteMatchesMutation = useMutation({
    mutationFn: () => api.deleteMatches(id!, {
      query: debouncedSnippetsSearch || undefined,
      language: selectedLanguage || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source-snippets", id] });
      queryClient.invalidateQueries({ queryKey: ["source", id] });
      setDeleteMatchesModalOpen(false);
      if (snippets?.total === 0) {
        setSnippetsSearch("");
      }
    },
    onError: (error) => {
      console.error("Failed to delete matches:", error);
      toast.error(
        "Failed to delete matches: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const updateSourceNameMutation = useMutation({
    mutationFn: ({ name, version }: { name: string; version?: string }) =>
      api.updateSourceName(id!, name, version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["source", id] });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error) => {
      console.error("Failed to update source name:", error);
      throw error;
    },
  });


  // Computed values
  const snippetsTotalPages = useMemo(
    () => (snippets ? Math.ceil(snippets.total / snippetsPerPage) : 0),
    [snippets]
  );

  const docsTotalPages = useMemo(
    () => (documents ? Math.ceil(documents.total / docsPerPage) : 0),
    [documents]
  );

  return {
    id,
    activeTab,
    snippetsPage,
    docsPage,
    snippetsSearch,
    selectedLanguage,
    deleteModalOpen,
    deleteMatchesModalOpen,
    debouncedSnippetsSearch,
    snippetsPerPage,
    docsPerPage,
    snippetsTotalPages,
    docsTotalPages,
    handleTabChange,
    setSnippetsPage,
    setDocsPage,
    setSnippetsSearch,
    setSelectedLanguage,
    setDeleteModalOpen,
    setDeleteMatchesModalOpen,
    deleteMutation,
    deleteMatchesMutation,
    updateSourceNameMutation,
    source,
    documents,
    snippets,
    languages,
    docsLoading,
    snippetsLoading,
    sourceLoading,
    sourceError,
  };
}
