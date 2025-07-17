import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Link, useNavigate } from "react-router-dom";
import {
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  X,
  StopCircle,
  Trash2,
  Search,
  Check,
} from "lucide-react";
import ProgressBar from "../components/ProgressBar";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { NewCrawlDialog } from "../components/NewCrawlDialog";

export default function CrawlJobs() {
  const [showModal, setShowModal] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [jobToCancel, setJobToCancel] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set());
  const [isBulkDelete, setIsBulkDelete] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const {
    data: jobs,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["crawl-jobs"],
    queryFn: () => {
      return api.getCrawlJobs();
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const createMutation = useMutation({
    mutationFn: api.createCrawlJob.bind(api),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setShowModal(false);
      navigate(`/crawl/${(data as { id: string }).id}`);
    },
    onError: (error) => {
      console.error("Failed to create crawl job:", error);
      alert(
        "Failed to create crawl job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const handleSubmit = (formData: {
    name?: string;
    base_url: string;
    max_depth: number;
    domain_filter?: string;
    url_patterns?: string[];
    max_concurrent_crawls?: number;
  }) => {
    createMutation.mutate(formData);
  };

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => api.cancelCrawlJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setCancelModalOpen(false);
      setJobToCancel(null);
    },
    onError: (error) => {
      console.error("Failed to cancel job:", error);
      alert(
        "Failed to cancel job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const handleCancelClick = (job: { id: string; name: string }) => {
    setJobToCancel(job);
    setCancelModalOpen(true);
  };

  const confirmCancel = () => {
    if (jobToCancel) {
      cancelMutation.mutate(jobToCancel.id);
    }
  };

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => api.deleteCrawlJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setDeleteModalOpen(false);
      setJobToDelete(null);
    },
    onError: (error) => {
      console.error("Failed to delete job:", error);
      alert(
        "Failed to delete job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (jobIds: string[]) => api.deleteBulkCrawlJobs(jobIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setDeleteModalOpen(false);
      setSelectedJobs(new Set());
      setIsBulkDelete(false);
    },
    onError: (error) => {
      console.error("Failed to delete jobs:", error);
      alert(
        "Failed to delete jobs: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  // Filter jobs based on search query
  const filteredJobs = useMemo(() => {
    if (!jobs) return [];
    if (!searchQuery) return jobs;

    const query = searchQuery.toLowerCase();
    return jobs.filter(
      (job) =>
        job.name.toLowerCase().includes(query) ||
        job.base_url.toLowerCase().includes(query)
    );
  }, [jobs, searchQuery]);

  // Only allow deletion of completed, failed, or cancelled jobs
  const deletableJobs = useMemo(() => {
    return filteredJobs.filter((job) =>
      ["completed", "failed", "cancelled"].includes(job.status)
    );
  }, [filteredJobs]);

  const handleDeleteClick = (
    e: React.MouseEvent,
    job: { id: string; name: string }
  ) => {
    e.preventDefault();
    e.stopPropagation();
    setJobToDelete(job);
    setIsBulkDelete(false);
    setDeleteModalOpen(true);
  };

  const handleBulkDelete = () => {
    setIsBulkDelete(true);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (isBulkDelete) {
      bulkDeleteMutation.mutate(Array.from(selectedJobs));
    } else if (jobToDelete) {
      deleteMutation.mutate(jobToDelete.id);
    }
  };

  const toggleSelectJob = (jobId: string) => {
    const newSelected = new Set(selectedJobs);
    if (newSelected.has(jobId)) {
      newSelected.delete(jobId);
    } else {
      newSelected.add(jobId);
    }
    setSelectedJobs(newSelected);
  };

  const selectAll = () => {
    const allIds = new Set(deletableJobs.map((j) => j.id));
    setSelectedJobs(allIds);
  };

  const deselectAll = () => {
    setSelectedJobs(new Set());
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-destructive" />;
      case "running":
        return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading crawl jobs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">
          Error loading crawl jobs:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Crawl Jobs</h1>
          <p className="text-muted-foreground mt-2">
            Monitor and manage documentation crawls
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Crawl
        </button>
      </div>

      {/* Search and Selection Controls */}
      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search jobs by name or URL..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Bulk Actions Bar */}
        {deletableJobs.length > 0 && (
          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-md">
            <div className="flex items-center gap-4">
              {/* Select All Checkbox */}
              <div className="flex items-center gap-2">
                <div
                  onClick={() => {
                    if (
                      selectedJobs.size === deletableJobs.length &&
                      deletableJobs.length > 0
                    ) {
                      deselectAll();
                    } else {
                      selectAll();
                    }
                  }}
                  className="cursor-pointer"
                >
                  <div
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                      selectedJobs.size === deletableJobs.length &&
                      deletableJobs.length > 0
                        ? "bg-primary border-primary"
                        : selectedJobs.size > 0 &&
                          selectedJobs.size < deletableJobs.length
                        ? "bg-primary/50 border-primary"
                        : "border-input bg-background"
                    }`}
                  >
                    {selectedJobs.size === deletableJobs.length &&
                      deletableJobs.length > 0 && (
                        <Check className="h-3 w-3 text-primary-foreground" />
                      )}
                    {selectedJobs.size > 0 &&
                      selectedJobs.size < deletableJobs.length && (
                        <div className="w-2 h-2 bg-primary-foreground rounded-sm" />
                      )}
                  </div>
                </div>
                <span className="text-sm font-medium">
                  {selectedJobs.size} of {deletableJobs.length} deletable
                  selected
                </span>
              </div>
              <button
                onClick={selectAll}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Select all deletable {searchQuery && "matching"}
              </button>
              {selectedJobs.size > 0 && (
                <>
                  <span className="text-muted-foreground">•</span>
                  <button
                    onClick={deselectAll}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    Clear selection
                  </button>
                </>
              )}
            </div>
            <button
              onClick={handleBulkDelete}
              disabled={selectedJobs.size === 0}
              className={`px-4 py-2 rounded-md transition-colors ${
                selectedJobs.size > 0
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : "bg-secondary text-muted-foreground cursor-not-allowed"
              }`}
            >
              Delete Selected
            </button>
          </div>
        )}
      </div>

      {jobs && jobs.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No crawl jobs found. Create one to get started.
        </div>
      )}

      {filteredJobs.length === 0 && jobs && jobs.length > 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No jobs match your search.
        </div>
      )}

      {filteredJobs.length > 0 && (
        <div className="bg-secondary/50 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="w-12 px-6 py-3"></th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  URLs
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Snippets
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredJobs.map((job) => {
                const isDeletable = [
                  "completed",
                  "failed",
                  "cancelled",
                ].includes(job.status);
                return (
                  <tr key={job.id} className="hover:bg-secondary/80">
                    <td className="w-12 px-6 py-4">
                      {isDeletable && (
                        <div
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSelectJob(job.id);
                          }}
                          className="cursor-pointer"
                        >
                          <div
                            className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                              selectedJobs.has(job.id)
                                ? "bg-primary border-primary"
                                : "border-input bg-background hover:border-primary"
                            }`}
                          >
                            {selectedJobs.has(job.id) && (
                              <Check className="h-3 w-3 text-primary-foreground" />
                            )}
                          </div>
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link
                        to={`/crawl/${job.id}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {job.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {job.base_url}
                      </p>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(job.status)}
                        <span className="text-sm capitalize">{job.status}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {job.status === "running" ? (
                        <div className="w-32">
                          <ProgressBar
                            current={job.crawl_progress || 0}
                            total={100}
                            showPercentage={false}
                            height="h-1.5"
                          />
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {job.crawl_phase ? job.crawl_phase : "crawling"}
                          </div>
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {job.urls_crawled}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {job.snippets_extracted}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {new Date(job.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="flex items-center gap-2">
                        {(job.status === "running" ||
                          job.status === "paused") && (
                          <button
                            onClick={() => handleCancelClick(job)}
                            className="text-destructive hover:text-destructive/80 flex items-center gap-1"
                            title="Cancel job"
                          >
                            <StopCircle className="h-4 w-4" />
                            Cancel
                          </button>
                        )}
                        {isDeletable && (
                          <button
                            onClick={(e) => handleDeleteClick(e, job)}
                            className="text-muted-foreground hover:text-destructive flex items-center gap-1"
                            title="Delete job"
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* New Crawl Dialog */}
      <NewCrawlDialog
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending}
      />

      {/* Cancel Confirmation Modal */}
      <ConfirmationDialog
        isOpen={cancelModalOpen}
        title="Confirm Cancel"
        message={`Are you sure you want to cancel the job "${jobToCancel?.name}"? This action cannot be undone.`}
        confirmText="Cancel Job"
        cancelText="Keep Running"
        variant="destructive"
        isConfirming={cancelMutation.isPending}
        onConfirm={confirmCancel}
        onCancel={() => setCancelModalOpen(false)}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmationDialog
        isOpen={deleteModalOpen}
        title="Confirm Delete"
        message={
          isBulkDelete
            ? `Are you sure you want to delete ${selectedJobs.size} job${
                selectedJobs.size > 1 ? "s" : ""
              }? This will permanently remove all associated documents and code snippets.`
            : `Are you sure you want to delete the job "${jobToDelete?.name}"? This will permanently remove all associated documents and code snippets.`
        }
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={deleteMutation.isPending || bulkDeleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => {
          setDeleteModalOpen(false);
          setIsBulkDelete(false);
        }}
      />
    </div>
  );
}
