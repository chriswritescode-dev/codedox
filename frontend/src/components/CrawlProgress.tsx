import { CrawlJob } from '../lib/api'
import ProgressBar from './ProgressBar'
import { Globe, Database, Zap } from 'lucide-react'

interface CrawlProgressProps {
  job: CrawlJob
  currentUrl?: string
}

export default function CrawlProgress({ job, currentUrl }: CrawlProgressProps) {
  const getPhaseBadge = () => {
    if (!job.crawl_phase || job.status !== "running") return null;

    const phaseConfig = {
      crawling: {
        label: "Crawling Pages",
        icon: <Globe className="h-4 w-4" />,
        color: "bg-blue-500 text-white",
      },
      enriching: {
        label: "Enriching Content",
        icon: <Database className="h-4 w-4" />,
        color: "bg-purple-500 text-white",
      },
      finalizing: {
        label: "Finalizing",
        icon: <Zap className="h-4 w-4" />,
        color: "bg-green-500 text-white",
      },
    };

    const config = phaseConfig[job.crawl_phase];
    if (!config) return null;

    return (
      <div
        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm ${config.color}`}
      >
        {config.icon}
        {config.label}
      </div>
    );
  };

  return (
    <div className="bg-secondary/50 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Progress</h3>
        {getPhaseBadge()}
      </div>

      {/* Overall Progress */}
      <div>
        <ProgressBar
          current={
            job.crawl_progress ||
            Math.min(
              100,
              Math.round((job.urls_crawled / job.total_pages) * 100 || 0)
            )
          }
          total={100}
          label="Pages Crawled"
        />
        <div className="flex justify-between text-sm text-muted-foreground mt-1">
          <span>
            {job.urls_crawled} of {job.total_pages} pages
          </span>
        </div>
      </div>

      {/* Enrichment Progress */}
      {job.crawl_phase === "enriching" &&
        job.documents_crawled &&
        job.documents_enriched !== undefined && (
          <div>
            <ProgressBar
              current={
                job.enrichment_progress ||
                Math.min(
                  100,
                  Math.round(
                    (job.documents_enriched / job.documents_crawled) * 100 || 0
                  )
                )
              }
              total={100}
              label="Documents Enriched"
            />
            <div className="text-sm text-muted-foreground mt-1">
              {job.documents_enriched} of {job.documents_crawled} documents
            </div>
          </div>
        )}

      {/* Current URL */}
      {currentUrl && job.status === "running" && (
        <div className="pt-2">
          <p className="text-sm text-muted-foreground mb-1">
            Currently processing:
          </p>
          <p className="text-sm font-mono bg-background p-2 rounded truncate">
            {currentUrl}
          </p>
        </div>
      )}

      {/* Statistics */}
      <div className="grid grid-cols-2 gap-4 pt-2">
        <div>
          <p className="text-sm text-muted-foreground">Snippets Extracted</p>
          <p className="text-xl font-semibold">{job.snippets_extracted}</p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Avg. Snippets/Page</p>
          <p className="text-xl font-semibold">
            {job.urls_crawled > 0
              ? (job.snippets_extracted / job.urls_crawled).toFixed(1)
              : "0"}
          </p>
        </div>
      </div>
    </div>
  );
}