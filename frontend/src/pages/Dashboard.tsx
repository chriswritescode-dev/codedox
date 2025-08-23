import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { FileText, Code, Database, Clock, Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import QuickSearch from '../components/QuickSearch'
import { NewCrawlDialog } from '../components/NewCrawlDialog'
import { useToast } from '../hooks/useToast'

export default function Dashboard() {
  const [showNewCrawlDialog, setShowNewCrawlDialog] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()
  
  
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['statistics'],
    queryFn: () => api.getStatistics(),
  })

  const createCrawlMutation = useMutation({
    mutationFn: (data: Parameters<typeof api.createCrawlJob>[0]) => api.createCrawlJob(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['statistics'] })
      queryClient.invalidateQueries({ queryKey: ['crawl-jobs'] })
      setShowNewCrawlDialog(false)
      navigate(`/crawl/${data.id}`)
    },
    onError: (error) => {
      console.error('Failed to create crawl job:', error)
      toast.error(`Failed to create crawl job: ${error.message || 'Unknown error'}`)
    },
  })

  const handleCreateCrawl = (formData: {
    name?: string
    base_url: string
    max_depth: number
    max_pages?: number
    domain_filter?: string
    url_patterns?: string[]
    max_concurrent_crawls?: number
  }) => {
    createCrawlMutation.mutate(formData)
  }
  

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading statistics...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Error loading statistics</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full py-8">
      <div className="flex-1 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">CodeDox Dashboard</h1>
          <button
            onClick={() => setShowNewCrawlDialog(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Crawl
          </button>
        </div>

        <QuickSearch />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-secondary/50 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Sources</p>
                <p className="text-2xl font-semibold">
                  {stats?.total_sources || 0}
                </p>
              </div>
              <Database className="h-8 w-8 text-muted-foreground" />
            </div>
          </div>

          <div className="bg-secondary/50 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Documents</p>
                <p className="text-2xl font-semibold">
                  {stats?.total_documents || 0}
                </p>
              </div>
              <FileText className="h-8 w-8 text-muted-foreground" />
            </div>
          </div>

          <div className="bg-secondary/50 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Code Snippets</p>
                <p className="text-2xl font-semibold">
                  {stats?.total_snippets || 0}
                </p>
              </div>
              <Code className="h-8 w-8 text-muted-foreground" />
            </div>
          </div>

          <div className="bg-secondary/50 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Languages</p>
                <p className="text-2xl font-semibold">
                  {stats?.languages ? Object.keys(stats.languages).length : 0}
                </p>
              </div>
              <Code className="h-8 w-8 text-muted-foreground" />
            </div>
          </div>
        </div>

        {stats?.languages && Object.keys(stats.languages).length > 0 && (
          <div className="bg-secondary/50 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">
              Language Distribution
            </h2>
            <div className="space-y-2 overflow-y-auto h-[200px] border border-white/90! p-1 px-2 rounded-md">
              {Object.entries(stats.languages)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 10)
                .map(([language, count]) => (
                  <div
                    key={language}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm">{language}</span>
                    <span className="text-sm text-muted-foreground">
                      {count} snippets
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {stats?.recent_crawls && stats.recent_crawls.length > 0 && (
          <div className="bg-secondary/50 rounded-lg p-6 mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Recent Crawls</h2>
              <Link
                to="/crawl"
                className="text-sm text-primary hover:underline"
              >
                View all
              </Link>
            </div>
            <div className="space-y-3 overflow-y-auto h-[450px] shadow-lg">
              {stats.recent_crawls.map((crawl) => (
                <Link
                  key={crawl.id}
                  to={`/crawl/${crawl.id}`}
                  className="block p-3 bg-background rounded-md hover:bg-secondary transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{crawl.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {crawl.urls_crawled} URLs • {crawl.snippets_extracted}{" "}
                        snippets
                      </p>
                    </div>
                    <div className="flex items-center text-sm text-muted-foreground">
                      <Clock className="h-4 w-4 mr-1" />
                      {new Date(crawl.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        <NewCrawlDialog
          isOpen={showNewCrawlDialog}
          onClose={() => setShowNewCrawlDialog(false)}
          onSubmit={handleCreateCrawl}
          isSubmitting={createCrawlMutation.isPending}
        />
      </div>
    </div>
  );
}
