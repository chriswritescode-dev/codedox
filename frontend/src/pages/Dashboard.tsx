import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { FileText, Code, Database, Clock } from "lucide-react";
import { Link } from "react-router-dom";
import QuickSearch from "../components/QuickSearch";

export default function Dashboard() {
  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["statistics"],
    queryFn: () => api.getStatistics(),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading statistics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Error loading statistics</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full py-8">
      <div className="flex-1 space-y-6">
        <h1 className="text-center text-3xl font-bold">CODEDOX Dashboard</h1>

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

        {stats?.recent_jobs && stats.recent_jobs.length > 0 && (
          <div className="bg-secondary/50 rounded-lg p-6 mb-10">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Recent Jobs</h2>
              <Link
                to="/crawl"
                className="text-sm text-primary hover:underline"
              >
                View all
              </Link>
            </div>
            <div className="space-y-3 overflow-y-auto h-[450px] shadow-lg">
              {stats.recent_jobs.map((job) => {
                const jobType =
                  "job_type" in job
                    ? job.job_type
                    : "base_url" in job
                      ? "crawl"
                      : "upload";
                // Link to appropriate detail page based on job type
                const linkPath =
                  jobType === "crawl"
                    ? `/crawl/${job.id}`
                    : `/sources/${job.id}`; // Upload jobs go to source detail page

                const content = (
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{job.name}</p>
                        <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full">
                          {jobType === "crawl" ? "Crawl" : "Upload"}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {job.snippets_extracted} snippets
                        {jobType === "crawl" && "urls_crawled" in job && (
                          <span> • {job.urls_crawled} pages</span>
                        )}
                        {jobType === "upload" && "file_count" in job && (
                          <span> • {job.file_count} files</span>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center text-sm text-muted-foreground">
                      <Clock className="h-4 w-4 mr-1" />
                      {new Date(job.created_at).toLocaleDateString()}
                    </div>
                  </div>
                );

                return (
                  <Link
                    key={job.id}
                    to={linkPath}
                    className="block p-3 bg-background rounded-md hover:bg-secondary transition-colors"
                  >
                    {content}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
