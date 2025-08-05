import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useWebSocket } from "../hooks/useWebSocket";
import {
  ArrowLeft,
  Briefcase,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  StopCircle,
  PlayCircle,
  AlertCircle,
} from "lucide-react";
import CrawlProgress from "../components/CrawlProgress";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { FailedPagesList } from "../components/FailedPagesList";

export default function CrawlDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [currentUrl, setCurrentUrl] = useState<string>();
  const [showFailedPages, setShowFailedPages] = useState(false);

  // WebSocket for real-time updates
  const { subscribe, unsubscribe } = useWebSocket({
    onMessage: (message) => {
      if (message.type === "crawl_update" && message.job_id === id) {
        // Update current URL if provided
        if (message.data?.current_url) {
          setCurrentUrl(message.data.current_url);
        }
        // Invalidate the query to refresh the data
        queryClient.invalidateQueries({ queryKey: ["crawl-job", id] });
      }
    },
  });

  // Subscribe to updates for this job
  useEffect(() => {
    if (id) {
      subscribe(id);
      return () => unsubscribe(id);
    }
  }, [id, subscribe, unsubscribe]);

  const {
    data: job,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["crawl-job", id],
    queryFn: () => api.getCrawlJob(id!),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 5000 : false, // Refresh every 5s if running (backup for WebSocket)
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelCrawlJob(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-job", id] });
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setCancelModalOpen(false);
    },
    onError: (error) => {
      console.error("Failed to cancel job:", error);
      alert(
        "Failed to cancel job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const recrawlMutation = useMutation({
    mutationFn: (urls?: string[]) => api.recrawlJob(id!, urls),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["crawl-job", id] });
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      // Navigate to the new job
      window.location.href = `/crawl/${data.new_job_id}`;
    },
    onError: (error) => {
      console.error("Failed to recrawl job:", error);
      alert(
        "Failed to recrawl job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const {
    data: failedPages,
    isLoading: isLoadingFailedPages,
  } = useQuery({
    queryKey: ["crawl-job-failed-pages", id],
    queryFn: () => api.getFailedPages(id!),
    enabled: !!id && showFailedPages && job?.failed_pages_count !== undefined && job.failed_pages_count > 0,
  });

  const confirmCancel = () => {
    cancelMutation.mutate();
  };

  const handleRecrawl = () => {
    if (confirm("Are you sure you want to recrawl this job? This will create a new crawl job with the same configuration.")) {
      recrawlMutation.mutate();
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case "failed":
        return <XCircle className="h-6 w-6 text-destructive" />;
      case "running":
        return <Loader2 className="h-6 w-6 text-primary animate-spin" />;
      default:
        return <Clock className="h-6 w-6 text-muted-foreground" />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading crawl job...</div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">Error loading crawl job</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-4">
        <Link
          to="/crawl"
          className="flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to crawl jobs
        </Link>
      </div>

      <div className="bg-secondary/50 rounded-lg p-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <Briefcase className="h-8 w-8 text-muted-foreground" />
            <div>
              <h1 className="text-2xl font-bold">{job.name}</h1>
              <p className="text-sm text-muted-foreground">{job.base_url}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              {getStatusIcon(job.status)}
              <span className="text-lg font-medium capitalize">
                {job.status}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {(job.status === "running" || job.status === "paused") && (
                <button
                  onClick={() => setCancelModalOpen(true)}
                  className="cursor-pointer flex items-center gap-2 px-3 py-1.5 text-destructive border border-destructive rounded-md hover:bg-destructive/10 hover:border-red-500"
                >
                  <StopCircle className="h-4 w-4" />
                  Cancel
                </button>
              )}
              {(job.status === "failed" || job.status === "completed") && (
                <button
                  onClick={() => handleRecrawl()}
                  disabled={recrawlMutation.isPending}
                  className="cursor-pointer flex items-center gap-2 px-3 py-1.5 text-primary border border-primary rounded-md hover:bg-primary/10 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {recrawlMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <PlayCircle className="h-4 w-4" />
                  )}
                  Recrawl
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-background rounded-md p-4">
            <p className="text-sm text-muted-foreground mb-1">Max Depth</p>
            <p className="text-xl font-semibold">{job.max_depth}</p>
          </div>

          <div className="bg-background rounded-md p-4">
            <p className="text-sm text-muted-foreground mb-1">URLs Crawled</p>
            <p className="text-xl font-semibold">{job.urls_crawled}</p>
          </div>

          <div className="bg-background rounded-md p-4">
            <p className="text-sm text-muted-foreground mb-1">
              Snippets Extracted
            </p>
            <p className="text-xl font-semibold">{job.snippets_extracted}</p>
          </div>

          {job.failed_pages_count !== undefined && job.failed_pages_count > 0 && (
            <div 
              className="bg-orange-50 dark:bg-orange-900/20 rounded-md p-4 border border-orange-200 dark:border-orange-800 cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors"
              onClick={() => setShowFailedPages(!showFailedPages)}
            >
              <p className="text-sm text-orange-700 dark:text-orange-300 mb-1">Failed Pages</p>
              <div className="flex items-center justify-between">
                <p className="text-xl font-semibold text-orange-900 dark:text-orange-100">{job.failed_pages_count}</p>
                <AlertCircle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
              </div>
              <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">Click to view</p>
            </div>
          )}

          <div className="bg-background rounded-md p-4">
            <p className="text-sm text-muted-foreground mb-1">Created</p>
            <p className="text-sm font-medium">
              {new Date(job.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        {job.completed_at && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Completed: {new Date(job.completed_at).toLocaleString()}
            </p>
          </div>
        )}

        {job.error_message && (
          <div className="mt-4 p-4 bg-destructive/10 text-destructive rounded-md">
            <p className="font-medium mb-1">Error</p>
            <p className="text-sm">{job.error_message}</p>
          </div>
        )}
      </div>

      {/* Progress Section */}
      {job.status === "running" && (
        <CrawlProgress job={job} currentUrl={currentUrl} />
      )}

      {/* Failed Pages Section */}
      {showFailedPages && job.failed_pages_count !== undefined && job.failed_pages_count > 0 && (
        <div className="bg-secondary/50 rounded-lg p-6">
          {isLoadingFailedPages ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading failed pages...</span>
            </div>
          ) : failedPages && failedPages.length > 0 ? (
            <FailedPagesList
              pages={failedPages}
              onRetrySelected={(urls) => {
                if (confirm(`Are you sure you want to retry ${urls.length} failed page(s)?`)) {
                  recrawlMutation.mutate(urls);
                }
              }}
              isRetrying={recrawlMutation.isPending}
            />
          ) : (
            <p className="text-center text-muted-foreground py-8">No failed pages data available</p>
          )}
        </div>
      )}

      {/* Cancel Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        title="Confirm Cancel"
        message={`Are you sure you want to cancel the job "${job.name}"? This action cannot be undone.`}
        confirmText="Cancel Job"
        cancelText="Keep Running"
        onConfirm={confirmCancel}
        onCancel={() => setCancelModalOpen(false)}
        variant="destructive"
        isConfirming={cancelMutation.isPending}
      />
    </div>
  );
}
