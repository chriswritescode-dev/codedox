import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, CodeSnippet } from "../lib/api";
import { useDebounce } from "./useDebounce";

interface DocumentDetailState {
  sourceId: string;
  documentId: string;
  currentPage: number;
  searchQuery: string;
  selectedLanguage: string;
  debouncedSearchQuery: string;
  
  // Computed values
  itemsPerPage: number;
  totalPages: number;
  languages: { languages: { name: string; count: number }[] } | undefined;
  
  // Handlers
  setCurrentPage: (page: number) => void;
  setSearchQuery: (search: string) => void;
  setSelectedLanguage: (lang: string) => void;
  
  // Query data
  data: {
    document: {
      id: number;
      url: string;
      title: string;
      crawl_depth: number;
      created_at: string;
    };
    source: {
      id: string;
      name: string;
      type: string;
    } | null;
    snippets: CodeSnippet[];
    total: number;
    limit: number;
    offset: number;
  } | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function useDocumentDetail(sourceId?: string, documentId?: string): DocumentDetailState {
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Basic state
  const [currentPage, setCurrentPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState(searchParams.get("search") || "");
  const [selectedLanguage, setSelectedLanguage] = useState(searchParams.get("language") || "");
  
  // Pagination settings
  const itemsPerPage = 10;
  
  // Debounce search query
  const debouncedSearchQuery = useDebounce(searchQuery, 300);
  
  // Data query
  const {
    data,
    isLoading,
    error,
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
  });
  
  // Extract unique languages from current results in SourceDetail format
  const languages = useMemo(() => {
    if (!data?.snippets) return undefined;
    const langCounts = new Map<string, number>();
    
    data.snippets.forEach(snippet => {
      if (snippet.language) {
        langCounts.set(snippet.language, (langCounts.get(snippet.language) || 0) + 1);
      }
    });
    
    if (langCounts.size === 0) return undefined;
    
    const languagesArray = Array.from(langCounts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name));
    
    return { languages: languagesArray };
  }, [data?.snippets]);
  
  const totalPages = useMemo(
    () => (data ? Math.ceil(data.total / itemsPerPage) : 0),
    [data]
  );
  
  // Reset page when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearchQuery, selectedLanguage]);
  
  // Sync state with URL
  useEffect(() => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev);
      
      if (debouncedSearchQuery) {
        newParams.set('search', debouncedSearchQuery);
      } else {
        newParams.delete('search');
      }
      
      if (selectedLanguage) {
        newParams.set('language', selectedLanguage);
      } else {
        newParams.delete('language');
      }
      
      return newParams;
    }, { replace: true });
  }, [debouncedSearchQuery, selectedLanguage, setSearchParams]);
  
  return {
    sourceId: sourceId || '',
    documentId: documentId || '',
    currentPage,
    searchQuery,
    selectedLanguage,
    debouncedSearchQuery,
    itemsPerPage,
    totalPages,
    languages,
    setCurrentPage,
    setSearchQuery,
    setSelectedLanguage,
    data,
    isLoading,
    error,
  };
}