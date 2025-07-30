// Use environment variable with fallback to /api
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export interface Source {
  id: string
  name: string
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
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
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
  async getSources(): Promise<Source[]> {
    return this.fetch<Source[]>('/sources')
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

  async recrawlSource(id: string): Promise<CrawlJob> {
    return this.fetch<CrawlJob>(`/sources/${id}/recrawl`, {
      method: 'POST',
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

  async resumeCrawlJob(id: string): Promise<{ id: string; message: string }> {
    return this.fetch<{ id: string; message: string }>(`/crawl-jobs/${id}/resume`, {
      method: 'POST',
    })
  }

  async retryFailedPages(id: string): Promise<{ message: string; job_id: string; new_job_id: string }> {
    return this.fetch<{ message: string; job_id: string; new_job_id: string }>(`/crawl-jobs/${id}/retry-failed`, {
      method: 'POST',
    })
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

  // Search
  async search(params: {
    source_name?: string
    query?: string
    language?: string
    limit?: number
    offset?: number
  }): Promise<SearchResult[]> {
    const queryParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
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

  async formatSnippet(
    id: string,
    save: boolean = false
  ): Promise<{
    original: string
    formatted: string
    language: string
    changed: boolean
    saved: boolean
    detected_language?: string
    formatter_used?: string
  }> {
    return this.fetch(`/snippets/${id}/format`, {
      method: 'POST',
      body: JSON.stringify({ save })
    })
  }

  async formatSource(
    id: string,
    save: boolean = false,
    dryRun: boolean = true
  ): Promise<{
    source_id: string
    source_name: string
    total_snippets: number
    changed_snippets: number
    saved_snippets: number
    preview: Array<{
      snippet_id: number
      title: string
      language: string
      original_preview: string
      formatted_preview: string
    }>
  }> {
    return this.fetch(`/snippets/sources/${id}/format`, {
      method: 'POST',
      body: JSON.stringify({ save, dry_run: dryRun })
    })
  }

  // Upload
  async uploadMarkdown(data: {
    content: string
    source_url?: string
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
    sourceUrl?: string,
    title?: string
  ): Promise<{
    status: string
    document_id: string
    snippets_count: number
    message: string
  }> {
    const formData = new FormData()
    formData.append('file', file)
    if (sourceUrl) formData.append('source_url', sourceUrl)
    if (title) formData.append('title', title)

    return this.fetch('/upload/file', {
      method: 'POST',
      body: formData
    })
  }

  async uploadFiles(
    files: File[],
    title?: string
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
    if (title) formData.append('title', title)

    return this.fetch('/upload/files', {
      method: 'POST',
      body: formData
    })
  }
}

export const api = new APIClient()

// Export individual methods for convenience
export const uploadMarkdown = api.uploadMarkdown.bind(api)
export const uploadFile = api.uploadFile.bind(api)
export const uploadFiles = api.uploadFiles.bind(api)