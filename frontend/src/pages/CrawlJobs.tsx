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
  AlertCircle,
  PlayCircle,
} from "lucide-react";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { NewCrawlDialog } from "../components/NewCrawlDialog";
import { PaginationControls } from "../components/PaginationControls";
import { useToast } from "../hooks/useToast";

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
  const [isBulkCancel, setIsBulkCancel] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const {
    data: allJobs,
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
      toast.error(
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
      toast.error(
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
    if (isBulkCancel) {
      bulkCancelMutation.mutate(Array.from(selectedJobs));
    } else if (jobToCancel) {
      cancelMutation.mutate(jobToCancel.id);
    }
  };

  const handleBulkCancel = () => {
    setIsBulkCancel(true);
    setCancelModalOpen(true);
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
      toast.error(
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
      toast.error(
        "Failed to delete jobs: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const bulkCancelMutation = useMutation({
    mutationFn: (jobIds: string[]) => api.cancelBulkCrawlJobs(jobIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      setCancelModalOpen(false);
      setSelectedJobs(new Set());
      setIsBulkCancel(false);
    },
    onError: (error) => {
      console.error("Failed to cancel jobs:", error);
      toast.error(
        "Failed to cancel jobs: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  // Filter jobs based on search query
  const filteredJobs = useMemo(() => {
    if (!allJobs) return [];
    if (!searchQuery) return allJobs;

    const query = searchQuery.toLowerCase();
    return allJobs.filter(
      (job) =>
        job.name.toLowerCase().includes(query) ||
        job.base_url.toLowerCase().includes(query)
    );
  }, [allJobs, searchQuery]);

  // Paginate the filtered jobs
  const paginatedJobs = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredJobs.slice(startIndex, endIndex);
  }, [filteredJobs, currentPage, itemsPerPage]);

  // Only allow deletion of completed, failed, cancelled, or paused jobs
  const deletableJobs = useMemo(() => {
    return filteredJobs.filter((job) =>
      ["completed", "failed", "cancelled", "paused"].includes(job.status)
    );
  }, [filteredJobs]);

  // Jobs that can be cancelled (running or stalled)
  const cancellableJobs = useMemo(() => {
    return filteredJobs.filter((job) => job.status === "running");
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

  const recrawlMutation = useMutation({
    mutationFn: (jobId: string) => api.recrawlJob(jobId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["crawl-jobs"] });
      // Navigate to the new job detail page
      navigate(`/crawl/${(data as { new_job_id: string }).new_job_id}`);
    },
    onError: (error) => {
      console.error("Failed to recrawl job:", error);
      toast.error(
        "Failed to recrawl job: " +
          (error instanceof Error ? error.message : "Unknown error")
      );
    },
  });

  const handleRecrawlClick = (job: { id: string; name: string }) => {
    recrawlMutation.mutate(job.id);
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
    const allIds = new Set(filteredJobs.map((j) => j.id));
    setSelectedJobs(allIds);
  };

  const deselectAll = () => {
    setSelectedJobs(new Set());
  };

  // Check if a job is stalled (no heartbeat for 1+ minute)
  const isJobStalled = (job: any) => {
    if (job.status !== "running" || !job.last_heartbeat) return false;
    
    const lastHeartbeat = new Date(job.last_heartbeat).getTime();
    const now = new Date().getTime();
    const timeSinceHeartbeat = (now - lastHeartbeat) / 1000; // seconds
    
    return timeSinceHeartbeat > 60; // 1 minute
  };

  // Get time since last heartbeat in human-readable format
  const getTimeSinceHeartbeat = (job: any) => {
    if (!job.last_heartbeat) return null;
    
    const lastHeartbeat = new Date(job.last_heartbeat).getTime();
    const now = new Date().getTime();
    const seconds = Math.floor((now - lastHeartbeat) / 1000);
    
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleItemsPerPageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newItemsPerPage = parseInt(e.target.value);
    setItemsPerPage(newItemsPerPage);
    setCurrentPage(1); // Reset to first page when changing items per page
  };

  const getStatusIcon = (status: string, job: any) => {
    // Check for stalled state
    if (status === "running" && isJobStalled(job)) {
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    }
    
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-destructive" />;
      case "running":
        return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
      case "cancelled":
        return <StopCircle className="h-4 w-4 text-muted-foreground" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusText = (status: string, job: any) => {
    if (status === "running" && isJobStalled(job)) {
      return "stalled";
    }
    return status;
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
    <div className="flex flex-col h-full min-h-0">
      {/* Fixed header section */}
      <div className="space-y-4 pb-4">
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
          {!!searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        </div>
      </div>

      {!!allJobs && allJobs.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No crawl jobs found. Create one to get started.
        </div>
      )}

      {filteredJobs.length === 0 && !!allJobs && allJobs.length > 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No jobs match your search.
        </div>
      )}

      {filteredJobs.length > 0 && (
        <div className="flex-1 min-h-0 bg-secondary/50 rounded-lg overflow-hidden flex flex-col">
            {selectedJobs.size > 0 && (
              <div className="flex items-center justify-between p-4 bg-secondary/70 border-b border-border">
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium">
                    {selectedJobs.size} of {filteredJobs.length} selected
                  </span>
                  <button
                    onClick={selectAll}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    Select all
                  </button>
                  <button
                    onClick={deselectAll}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    Clear selection
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  {(() => {
                    const selectedCancellable = Array.from(selectedJobs).filter(id => 
                      cancellableJobs.some(job => job.id === id)
                    ).length;
                    const selectedDeletable = Array.from(selectedJobs).filter(id => 
                      deletableJobs.some(job => job.id === id)
                    ).length;
                    
                    return (
                      <>
                        {selectedCancellable > 0 && (
                          <button
                            onClick={handleBulkCancel}
                            className="px-3 py-1.5 text-sm rounded-md bg-yellow-600 text-white hover:bg-yellow-700"
                          >
                            Cancel {selectedCancellable} Running
                          </button>
                        )}
                        {selectedDeletable > 0 && (
                          <button
                            onClick={handleBulkDelete}
                            className="px-3 py-1.5 text-sm rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          >
                            Delete {selectedDeletable} Selected
                          </button>
                        )}
                      </>
                    );
                  })()}
                </div>
              </div>
            )}
            
            <div className="flex-1 min-h-0 overflow-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-secondary z-10 shadow-sm">
                  <tr className="border-b border-border">
                    <th className="w-12 px-6 py-3">
                      <div
                        onClick={() => {
                          if (
                            selectedJobs.size === filteredJobs.length &&
                            filteredJobs.length > 0
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
                            selectedJobs.size === filteredJobs.length &&
                            filteredJobs.length > 0
                              ? "bg-primary border-primary"
                              : selectedJobs.size > 0 &&
                                selectedJobs.size < filteredJobs.length
                              ? "bg-primary/50 border-primary"
                              : "border-input bg-background"
                          }`}
                        >
                          {selectedJobs.size === filteredJobs.length &&
                            filteredJobs.length > 0 && (
                              <Check className="h-3 w-3 text-primary-foreground" />
                            )}
                          {selectedJobs.size > 0 &&
                            selectedJobs.size < filteredJobs.length && (
                              <div className="w-2 h-2 bg-primary-foreground rounded-sm" />
                            )}
                        </div>
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Status
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
                  {paginatedJobs.map((job) => {
                    const isDeletable = [
                      "completed",
                      "failed",
                      "cancelled",
                    ].includes(job.status);
                    return (
                      <tr key={job.id} className="hover:bg-secondary/80">
                        <td className="w-12 px-6 py-4">
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
                            {getStatusIcon(job.status, job)}
                            <span className="text-sm capitalize">
                              {getStatusText(job.status, job)}
                            </span>
                            {job.status === "running" && !!job.last_heartbeat && (
                              <span className="text-xs text-muted-foreground">
                                ({getTimeSinceHeartbeat(job)})
                              </span>
                            )}
                          </div>
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
                            {/* Show recrawl button for failed/stalled jobs */}
                            {(job.status === "failed" || 
                              (job.status === "running" && isJobStalled(job))) && (
                              <button
                                onClick={() => handleRecrawlClick(job)}
                                className="text-primary hover:text-primary/80 flex items-center gap-1"
                                title="Recrawl job"
                              >
                                <PlayCircle className="h-4 w-4" />
                                Recrawl
                              </button>
                            )}
                            {(job.status === "running" && !isJobStalled(job)) && (
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
        message={
          isBulkCancel
            ? `Are you sure you want to cancel ${selectedJobs.size} running job${
                selectedJobs.size > 1 ? "s" : ""
              }? This action cannot be undone.`
            : `Are you sure you want to cancel the job "${jobToCancel?.name}"? This action cannot be undone.`
        }
        confirmText={isBulkCancel ? "Cancel Jobs" : "Cancel Job"}
        cancelText="Keep Running"
        variant="destructive"
        isConfirming={cancelMutation.isPending || bulkCancelMutation.isPending}
        onConfirm={confirmCancel}
        onCancel={() => {
          setCancelModalOpen(false);
          setIsBulkCancel(false);
        }}
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

      {allJobs && filteredJobs.length > 0 && (
        <div className="pt-4 mt-4 border-t border-border">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label htmlFor="items-per-page" className="text-sm text-muted-foreground">
                  Items per page:
                </label>
                <select
                  id="items-per-page"
                  value={itemsPerPage}
                  onChange={handleItemsPerPageChange}
                  className="w-20 px-2 py-1 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
          </div>
          
          <PaginationControls
            currentPage={currentPage}
            totalPages={Math.ceil(filteredJobs.length / itemsPerPage)}
            onPageChange={handlePageChange}
            totalItems={filteredJobs.length}
            itemsPerPage={itemsPerPage}
            currentItemsCount={paginatedJobs.length}
          />
        </div>
      )}
    </div>
  );
}
