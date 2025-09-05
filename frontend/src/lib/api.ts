// Use environment variable with fallback to /api
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export interface Source {
  id: string
  name: string
  version?: string | null
  base_url: string
  created_at: string
  updated_at: string
  documents_count: number
  snippets_count: number
}

export interface CrawlJob {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'
  base_url: string
  max_depth: number
  urls_crawled: number
  total_pages: number
  snippets_extracted: number
  failed_pages_count?: number
  crawl_phase?: 'crawling' | 'finalizing' | null
  documents_crawled?: number
  created_at: string
  started_at?: string
  completed_at?: string
  error_message?: string
  last_heartbeat?: string
  retry_count?: number
  crawl_progress?: number
}

export interface CodeSnippet {
  id: string
  title?: string
  code: string
  language: string
  description?: string
  source_url: string
  document_title: string
  file_path?: string
  start_line?: number
  end_line?: number
  created_at: string
  source_id?: string
  source_name?: string
}

export interface Document {
  id: number
  url: string
  title: string
  crawl_depth: number
  snippets_count: number
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface PaginatedDocuments {
  documents: Document[]
  total: number
  limit: number
  offset: number
}

export interface PaginatedSnippets {
  snippets: CodeSnippet[]
  total: number
  limit: number
  offset: number
}

export interface LanguageStat {
  name: string
  count: number
}

export interface SearchResult {
  snippet: CodeSnippet
  score: number
  highlights?: string[]
}

export interface Statistics {
  total_sources: number
  total_documents: number
  total_snippets: number
  languages: { [key: string]: number }
  recent_crawls: CrawlJob[]
}

class APIClient {
  async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    try {
      // Don't set Content-Type for FormData - browser will set it with boundary
      const isFormData = options?.body instanceof FormData;
      const headers = isFormData 
        ? { ...options?.headers }
        : {
            'Content-Type': 'application/json',
            ...options?.headers,
          };
      
      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
      }

      return response.json()
    } catch (error) {
      console.error('Fetch error:', error);
      throw error;
    }
  }

  // Dashboard
  async getStatistics(): Promise<Statistics> {
    return this.fetch<Statistics>('/statistics')
  }

  // Sources
  async getSources(params: { limit?: number; offset?: number } = {}): Promise<{
    sources: Source[]
    total: number
    limit: number
    offset: number
    has_next: boolean
    has_previous: boolean
  }> {
    const queryParams = new URLSearchParams()
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit))
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset))
    
    return this.fetch(`/sources?${queryParams}`)
  }

  async searchSources(
    params: { 
      query?: string
      min_snippets?: number
      max_snippets?: number
      limit?: number
      offset?: number 
    } = {}
  ): Promise<{
    sources: Source[]
    total: number
    limit: number
    offset: number
    has_next: boolean
    has_previous: boolean
    query: string | null
    filters: {
      min_snippets: number | null
      max_snippets: number | null
    }
  }> {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
    
    return this.fetch(`/sources/search?${queryParams}`)
  }

  async getSource(id: string): Promise<Source> {
    return this.fetch<Source>(`/sources/${id}`)
  }

  async getSourceDocuments(
    id: string,
    params: { limit?: number; offset?: number } = {}
  ): Promise<PaginatedDocuments> {
    const queryParams = new URLSearchParams()
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit))
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset))
    
    return this.fetch<PaginatedDocuments>(`/sources/${id}/documents?${queryParams}`)
  }

  async getSourceSnippets(
    id: string,
    params: { query?: string; language?: string; limit?: number; offset?: number } = {}
  ): Promise<PaginatedSnippets> {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, String(value))
      }
    })
    
    return this.fetch<PaginatedSnippets>(`/sources/${id}/snippets?${queryParams}`)
  }

  async getSourceLanguages(id: string): Promise<{ languages: LanguageStat[] }> {
    return this.fetch<{ languages: LanguageStat[] }>(`/sources/${id}/languages`)
  }

  async getDocumentSnippets(
    documentId: number,
    params: {
      query?: string
      language?: string
      limit?: number
      offset?: number
    } = {}
  ): Promise<{
    document: {
      id: number
      url: string
      title: string
      crawl_depth: number
      created_at: string
    }
    source: {
      id: string
      name: string
      type: string
    } | null
    snippets: CodeSnippet[]
    total: number
    limit: number
    offset: number
  }> {
    const queryParams = new URLSearchParams()
    if (params.query) queryParams.append('query', params.query)
    if (params.language) queryParams.append('language', params.language)
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit))
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset))
    
    return this.fetch(`/documents/${documentId}/snippets?${queryParams}`)
  }

  async getPageMarkdown(url: string): Promise<{
    status: string
    document?: {
      id: number
      url: string
      title: string
      last_crawled: string | null
      content_length?: number
    }
    source?: {
      id: string
      name: string
      type: string
    } | null
    markdown_content?: string
    metadata?: Record<string, any>
    message?: string
    note?: string
  }> {
    const queryParams = new URLSearchParams({ url })
    return this.fetch(`/documents/markdown?${queryParams}`)
  }

  async searchDocuments(
    query: string,
    params: { limit?: number; offset?: number } = {}
  ): Promise<{
    results: Array<{
      id: number
      url: string
      title: string
      source_name: string | null
      has_markdown: boolean
      last_crawled: string | null
    }>
    pagination: {
      total: number
      limit: number
      offset: number
      has_more: boolean
    }
    query: string
  }> {
    const queryParams = new URLSearchParams({ query })
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit))
    if (params.offset !== undefined) queryParams.append('offset', String(params.offset))
    
    return this.fetch(`/documents/search?${queryParams}`)
  }

  async deleteSource(id: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(`/sources/${id}`, {
      method: 'DELETE',
    })
  }

  async deleteBulkSources(ids: string[]): Promise<{ message: string; deleted_count: number }> {
    return this.fetch<{ message: string; deleted_count: number }>('/sources/bulk', {
      method: 'DELETE',
      body: JSON.stringify(ids),
    })
  }

  async deleteFilteredSources(params: {
    min_snippets?: number
    max_snippets?: number
    query?: string
  }): Promise<{ message: string; deleted_count: number }> {
    return this.fetch<{ message: string; deleted_count: number }>('/sources/bulk/delete-filtered', {
      method: 'POST',
      body: JSON.stringify(params),
    })
  }

  async countFilteredSources(params: {
    min_snippets?: number
    max_snippets?: number
    query?: string
  }): Promise<{ count: number; filters: { min_snippets?: number; max_snippets?: number; query?: string } }> {
    return this.fetch<{ count: number; filters: { min_snippets?: number; max_snippets?: number; query?: string } }>('/sources/bulk/count-filtered', {
      method: 'POST',
      body: JSON.stringify(params),
    })
  }

  async getFilteredSourceIds(params: {
    min_snippets?: number
    max_snippets?: number
    query?: string
  }): Promise<{ ids: string[]; total: number }> {
    return this.fetch<{ ids: string[]; total: number }>('/sources/ids', {
      method: 'POST',
      body: JSON.stringify(params),
    })
  }

  async deleteMatches(sourceId: string, params: { query?: string; language?: string } = {}): Promise<{ deleted_count: number; source_id: string; source_name: string }> {
    return this.fetch<{ deleted_count: number; source_id: string; source_name: string }>(`/snippets/sources/${sourceId}/delete-matches`, {
      method: 'POST',
      body: JSON.stringify({
        source_id: sourceId,
        query: params.query,
        language: params.language
      })
    })
  }

  async updateSourceName(id: string, name: string): Promise<Source> {
    return this.fetch<Source>(`/sources/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    })
  }

  async recrawlSource(id: string, ignoreHash: boolean = false): Promise<CrawlJob> {
    return this.fetch<CrawlJob>(`/sources/${id}/recrawl`, {
      method: 'POST',
      body: JSON.stringify({ ignore_hash: ignoreHash })
    })
  }

  // Crawl Jobs
  async getCrawlJobs(): Promise<CrawlJob[]> {
    return this.fetch<CrawlJob[]>('/crawl-jobs')
  }

  async getCrawlJob(id: string): Promise<CrawlJob> {
    return this.fetch<CrawlJob>(`/crawl-jobs/${id}`)
  }

  async createCrawlJob(data: {
    name?: string
    base_url: string
    max_depth: number
    max_pages?: number
    domain_filter?: string
    url_patterns?: string[]
    max_concurrent_crawls?: number
  }): Promise<CrawlJob> {
    return this.fetch<CrawlJob>('/crawl-jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async cancelCrawlJob(id: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(`/crawl-jobs/${id}/cancel`, {
      method: 'POST',
    })
  }

  async recrawlJob(id: string, urls?: string[]): Promise<{ message: string; original_job_id: string; new_job_id: string }> {
    return this.fetch<{ message: string; original_job_id: string; new_job_id: string }>(`/crawl-jobs/${id}/recrawl`, {
      method: 'POST',
      body: urls ? JSON.stringify({ urls }) : undefined,
    })
  }

  async getFailedPages(id: string): Promise<Array<{
    id: number
    url: string
    error_message: string | null
    failed_at: string | null
  }>> {
    return this.fetch<Array<{
      id: number
      url: string
      error_message: string | null
      failed_at: string | null
    }>>(`/crawl-jobs/${id}/failed-pages`)
  }

  async deleteCrawlJob(id: string): Promise<{ message: string }> {
    return this.fetch<{ message: string }>(`/crawl-jobs/${id}`, {
      method: 'DELETE',
    })
  }

  async deleteBulkCrawlJobs(ids: string[]): Promise<{ message: string; deleted_count: number }> {
    return this.fetch<{ message: string; deleted_count: number }>('/crawl-jobs/bulk', {
      method: 'DELETE',
      body: JSON.stringify(ids),
    })
  }

  async cancelBulkCrawlJobs(ids: string[]): Promise<{ message: string; cancelled_count: number }> {
    return this.fetch<{ message: string; cancelled_count: number }>('/crawl-jobs/bulk/cancel', {
      method: 'POST',
      body: JSON.stringify(ids),
    })
  }

  // Search
  async search(params: {
    source_name?: string
    query?: string
    language?: string
    search_mode?: string
    limit?: number
    offset?: number
  }): Promise<SearchResult[]> {
    const queryParams = new URLSearchParams()
    // Default to enhanced mode for better results
    const searchParams = { search_mode: 'enhanced', ...params }
    Object.entries(searchParams).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, String(value))
      }
    })
    
    return this.fetch<SearchResult[]>(`/search?${queryParams}`)
  }

  // Snippets
  async getSnippet(id: string): Promise<CodeSnippet> {
    return this.fetch<CodeSnippet>(`/snippets/${id}`)
  }


  // Upload
  async uploadMarkdown(data: {
    content: string
    name: string
    title?: string
  }): Promise<{
    status: string
    document_id: string
    snippets_count: number
    message: string
  }> {
    return this.fetch('/upload/markdown', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    })
  }

  async uploadFile(
    file: File,
    name: string,
    title?: string,
    maxConcurrent?: number
  ): Promise<{
    status: string
    document_id: string
    snippets_count: number
    message: string
  }> {
    const formData = new FormData()
    formData.append('file', file)
    if (name) formData.append('name', name)
    if (title) formData.append('title', title)
    if (maxConcurrent) formData.append('max_concurrent', maxConcurrent.toString())

    return this.fetch('/upload/file', {
      method: 'POST',
      body: formData
    })
  }

  async uploadFiles(
    files: File[],
    name: string,
    title?: string,
    version?: string,
    maxConcurrent?: number
  ): Promise<{
    status: string
    job_id: string
    file_count: number
    message: string
  }> {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    formData.append('name', name) // Always append name to ensure consistent source
    if (title) formData.append('title', title)
    if (version) formData.append('version', version)
    if (maxConcurrent) formData.append('max_concurrent', maxConcurrent.toString())

    return this.fetch('/upload/files', {
      method: 'POST',
      body: formData
    })
  }

  async uploadGitHubRepo(data: {
    repo_url: string
    name?: string
    version?: string
    path?: string
    branch?: string
    token?: string
    include_patterns?: string[]
    exclude_patterns?: string[]
    max_concurrent?: number
  }): Promise<{
    status: string
    job_id: string
    repository: string
    name: string
    path?: string
    branch: string
    message: string
  }> {
    return this.fetch('/upload/github', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    })
  }

  async getUploadStatus(jobId: string): Promise<{
    job_id: string
    name: string
    status: string
    file_count: number
    processed_files: number
    snippets_extracted: number
    created_at: string | null
    completed_at: string | null
    error_message: string | null
  }> {
    return this.fetch(`/upload/status/${jobId}`)
  }

  async getGitHubUploadStatus(jobId: string): Promise<{
    job_id: string
    name: string
    status: string
    file_count: number
    processed_files: number
    snippets_extracted: number
    created_at: string | null
    completed_at: string | null
    error_message: string | null
  }> {
    // Legacy method - redirects to unified status endpoint
    return this.getUploadStatus(jobId)
  }

  async getUploadConfig(): Promise<{
    max_file_size: number
    max_total_size: number
    batch_size: number
  }> {
    return this.fetch('/upload/config')
  }
}

export const api = new APIClient()

// Export individual methods for convenience
export const uploadMarkdown = api.uploadMarkdown.bind(api)
export const uploadFile = api.uploadFile.bind(api)
export const uploadFiles = api.uploadFiles.bind(api)
export const uploadGitHubRepo = api.uploadGitHubRepo.bind(api)
export const getUploadStatus = api.getUploadStatus.bind(api)
export const getGitHubUploadStatus = api.getGitHubUploadStatus.bind(api)
export const getUploadConfig = api.getUploadConfig.bind(api)