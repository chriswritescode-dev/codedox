import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { FileText, Code, Database, Clock } from 'lucide-react'
import { Link } from 'react-router-dom'
import QuickSearch from '../components/QuickSearch'

export default function Dashboard() {
  
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['statistics'],
    queryFn: () => {
      console.log('queryFn called for statistics');
      return api.getStatistics();
    },
  })
  

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
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">CodeDox Dashboard</h1>

      {/* Quick Search */}
      <QuickSearch />

      {/* Statistics Cards */}
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

      {/* Language Distribution */}
      {stats?.languages && Object.keys(stats.languages).length > 0 && (
        <div className="bg-secondary/50 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Language Distribution</h2>
          <div className="space-y-2">
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

      {/* Recent Crawls */}
      {stats?.recent_crawls && stats.recent_crawls.length > 0 && (
        <div className="bg-secondary/50 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Crawls</h2>
            <Link to="/crawl" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          <div className="space-y-3">
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
    </div>
  );
}