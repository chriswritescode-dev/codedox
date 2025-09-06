import { useState, useCallback, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Upload as UploadIcon,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  FileCode,
  Folder,
  GitBranch,
  Github,
  ArrowUp,
} from "lucide-react";
import {
  uploadMarkdown,
  uploadFiles,
  uploadGitHubRepo,
  getGitHubUploadStatus,
  getUploadStatus,
  getUploadConfig,
  api,
} from "../lib/api";
import { ConfirmationDialog } from '../components/ConfirmationDialog'

const allowedFileExtensions = ['md', 'txt', 'markdown', 'html', 'htm'];


export default function Upload() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Get active tab from URL params, default to "files"
  const tabParam = searchParams.get("tab");
  const activeTab = (tabParam === "github" ? "github" : "files") as "files" | "github";
  
  // Function to set active tab in URL
  const setActiveTab = (tab: "files" | "github") => {
    setSearchParams({ tab });
  };
  
  // Ensure valid tab parameter
  useEffect(() => {
    if (tabParam && tabParam !== "files" && tabParam !== "github") {
      setSearchParams({ tab: "files" });
    }
  }, [tabParam, setSearchParams]);

  // Scroll detection for back-to-top button
  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      setShowBackToTop(scrollTop > 100);
    };

    window.addEventListener('scroll', handleScroll);
    // Initial check
    handleScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  // Fetch upload configuration on mount
  useEffect(() => {
    getUploadConfig()
      .then(config => {
        setMaxTotalSize(config.max_total_size);
        setMaxFileSize(config.max_file_size);
        setBatchSize(config.batch_size || 500);
        setConfigLoaded(true);
      })
      .catch(error => {
        console.error("Failed to fetch upload config:", error);
        // Keep default values if fetch fails but allow uploads
        setConfigLoaded(true);
      });
  }, []);
  
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);
  
  // Upload configuration
  const [maxTotalSize, setMaxTotalSize] = useState<number>(1024 * 1024 * 1024); // 1GB default
  const [maxFileSize, setMaxFileSize] = useState<number>(10 * 1024 * 1024); // 10MB default
  const [batchSize, setBatchSize] = useState<number>(500); // Files per batch
  const [configLoaded, setConfigLoaded] = useState(false);
  const [maxConcurrent, setMaxConcurrent] = useState<number | string>(10); // Default concurrent file processing

  const [title, setTitle] = useState("");
  const [version, setVersion] = useState("");
  const [pastedContent, setPastedContent] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [directoryStructure, setDirectoryStructure] = useState<
    Map<string, File[]>
  >(new Map());

  // GitHub repo state
  const [repoUrl, setRepoUrl] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [repoBranch, setRepoBranch] = useState("main");
  const [repoToken, setRepoToken] = useState("");
  const [repoIncludePatterns, setRepoIncludePatterns] = useState("");
  const [repoExcludePatterns, setRepoExcludePatterns] = useState("");

  // Confirmation dialog state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [existingSourceInfo, setExistingSourceInfo] = useState<{
    name: string;
    version?: string;
    snippetCount: number;
    documentCount: number;
  } | null>(null);
  const [pendingUpload, setPendingUpload] = useState<
    (() => Promise<void>) | null
  >(null);
  const [checkingSource, setCheckingSource] = useState(false);
  
  const [showBackToTop, setShowBackToTop] = useState(false);

  // Validation helper functions
  const validateFileSize = useCallback((files: File[]): { valid: File[]; oversized: File[] } => {
    const valid: File[] = [];
    const oversized: File[] = [];
    
    files.forEach(file => {
      if (file.size > maxFileSize) {
        oversized.push(file);
      } else {
        valid.push(file);
      }
    });
    
    return { valid, oversized };
  }, [maxFileSize]);

  const validateTotalSize = useCallback((newFiles: File[]): string | null => {
    const currentSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);
    const newSize = newFiles.reduce((sum, f) => sum + f.size, 0);
    const totalSize = currentSize + newSize;
    
    if (totalSize > maxTotalSize) {
      return `Total file size exceeds ${formatFileSize(maxTotalSize)} limit. Current total: ${formatFileSize(totalSize)}`;
    }
    return null;
  }, [selectedFiles, maxTotalSize]);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      const validExtFiles = files.filter(
        (file) =>
          file.type === "text/markdown" ||
          file.type === "text/plain" || file.type === "text/html" ||
          allowedFileExtensions.some(ext => file.name.endsWith(`.${ext}`))
      );

      if (validExtFiles.length > 0) {
        // Check individual file sizes
        const { valid: validFiles, oversized } = validateFileSize(validExtFiles);
        
        if (oversized.length > 0) {
          const oversizedNames = oversized.map(f => `${f.name} (${formatFileSize(f.size)})`).join(', ');
          setError(
            `The following files exceed the ${formatFileSize(maxFileSize)} file size limit: ${oversizedNames}`
          );
          return;
        }

        // Check total size limit
        const sizeError = validateTotalSize(validFiles);
        if (sizeError) {
          setError(sizeError);
          return;
        }

        setSelectedFiles((prev) => [...prev, ...validFiles]);
        if (!title && validFiles.length === 1) {
          setTitle(validFiles[0].name.replace(/\.(md|txt|markdown|html|htm)$/, ""));
        }
      } else {
        setError(
          "Please upload markdown (.md, .markdown), HTML (.html, .htm), or text (.txt) files",
        );
      }
    },
    [title, selectedFiles, maxTotalSize, maxFileSize, validateFileSize, validateTotalSize],
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const validExtFiles = Array.from(files).filter(
        (file) =>
          file.type === "text/markdown" ||
          file.type === "text/plain" ||
          file.type === "text/html" ||
          allowedFileExtensions.some(ext => file.name.endsWith(`.${ext}`))
      );

      if (validExtFiles.length > 0) {
        // Check individual file sizes
        const { valid: validFiles, oversized } = validateFileSize(validExtFiles);
        
        if (oversized.length > 0) {
          const oversizedNames = oversized.map(f => `${f.name} (${formatFileSize(f.size)})`).join(', ');
          setError(
            `The following files exceed the ${formatFileSize(maxFileSize)} file size limit: ${oversizedNames}`
          );
          return;
        }

        // Check total size limit
        const sizeError = validateTotalSize(validFiles);
        if (sizeError) {
          setError(sizeError);
          return;
        }

        setSelectedFiles((prev) => [...prev, ...validFiles]);
        // Set title from first file if not already set
        if (!title && validFiles.length === 1) {
          setTitle(validFiles[0].name.replace(/\.(md|txt|markdown|html|htm)$/, ""));
        }
      } else {
        setError(
          "Please upload markdown (.md, .markdown), HTML (.html, .htm), or text (.txt) files",
        );
      }
    }
  };

  const handleDirectorySelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const fileArray = Array.from(files);
      const validExtFiles = fileArray.filter(
        (file) =>
          allowedFileExtensions.some(ext => file.name.endsWith(`.${ext}`))
      );

      if (validExtFiles.length > 0) {
        // Check individual file sizes
        const { valid: validFiles, oversized } = validateFileSize(validExtFiles);
        
        if (oversized.length > 0) {
          const oversizedNames = oversized.map(f => `${f.name} (${formatFileSize(f.size)})`).join(', ');
          setError(
            `The following files exceed the ${formatFileSize(maxFileSize)} file size limit: ${oversizedNames}`
          );
          return;
        }

        // Check total size limit
        const sizeError = validateTotalSize(validFiles);
        if (sizeError) {
          setError(sizeError);
          return;
        }

        // Group files by directory
        const dirMap = new Map<string, File[]>();
        validFiles.forEach((file) => {
          const path = (file as any).webkitRelativePath || file.name;
          const parts = path.split("/");
          const dirPath = parts.length > 1 ? parts.slice(0, -1).join("/") : "/";

          if (!dirMap.has(dirPath)) {
            dirMap.set(dirPath, []);
          }
          dirMap.get(dirPath)!.push(file);
        });

        setDirectoryStructure(dirMap);
        setSelectedFiles((prev) => [...prev, ...validFiles]);

        // Set title from directory name if not already set
        if (!title && validFiles.length > 0) {
          const firstPath = (validFiles[0] as any).webkitRelativePath || "";
          const rootDir = firstPath.split("/")[0];
          if (rootDir) {
            setTitle(rootDir);
          }
        }
      } else {
        setError(
          "No markdown (.md, .markdown), HTML (.html, .htm), or text (.txt) files found in the selected directory",
        );
      }
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const clearAllFiles = () => {
    setSelectedFiles([]);
    setDirectoryStructure(new Map());
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const checkForExistingSource = async (name: string, checkVersion?: string): Promise<boolean> => {
    setCheckingSource(true);
    try {
      const result = await api.searchSources({ query: name, limit: 100 });
      // Look for exact match on name AND version (case-insensitive for name)
      const exactMatch = result.sources.find(
        (source) => {
          const nameMatches = source.name.toLowerCase() === name.toLowerCase();
          // If no version specified in either the source or the check, only match on name
          // If version is specified, both must match
          const versionMatches = (!checkVersion && !source.version) || 
                                (checkVersion && source.version === checkVersion);
          return nameMatches && versionMatches;
        }
      );

      if (exactMatch) {
        setExistingSourceInfo({
          name: exactMatch.name,
          version: exactMatch.version || undefined,
          snippetCount: exactMatch.snippets_count || 0,
          documentCount: exactMatch.documents_count || 0,
        });
        return true;
      }
      return false;
    } catch (error) {
      console.error("Error checking for existing source:", error);
      // If we can't check, proceed without confirmation
      return false;
    } finally {
      setCheckingSource(false);
    }
  };

  const performGitHubUpload = async () => {
    setUploading(true);
    setError(null);
    setSuccess(null);
    setUploadProgress("Cloning repository...");

    try {
      // Parse patterns from comma-separated strings
      const includePatterns = repoIncludePatterns
        ? repoIncludePatterns
            .split(",")
            .map((p) => p.trim())
            .filter((p) => p)
        : undefined;
      const excludePatterns = repoExcludePatterns
        ? repoExcludePatterns
            .split(",")
            .map((p) => p.trim())
            .filter((p) => p)
        : undefined;

      // Extract repo name from URL if no title provided
      let uploadName = title;
      if (!uploadName) {
        const match = repoUrl.match(/\/([^/]+?)(?:\.git)?$/);
        uploadName = match ? match[1] : "Repository Documentation";
      }

      const result = await uploadGitHubRepo({
        repo_url: repoUrl,
        name: uploadName,
        version: version || undefined,
        path: repoPath || undefined,
        branch: repoBranch || "main",
        token: repoToken || undefined,
        include_patterns: includePatterns,
        exclude_patterns: excludePatterns,
        max_concurrent: typeof maxConcurrent === 'number' ? maxConcurrent : 10,
      });

      const jobId = result.job_id;
      setUploadProgress("Processing markdown files...");

      // Poll for status
      let status = null;
      let isProcessing = true;
      while (isProcessing) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        status = await getGitHubUploadStatus(jobId);

        if (status.processed_files > 0) {
          setUploadProgress(
            `Processing files: ${status.processed_files}/${status.file_count}`,
          );
          setUploadedCount(status.processed_files);
        }

        if (status.status === "completed" || status.status === "failed") {
          isProcessing = false;
        }
      }

      if (status?.status === "completed") {
        setSuccess(
          `Successfully processed ${status?.processed_files} files with ${status?.snippets_extracted} code snippets extracted`,
        );
        setTimeout(() => {
          navigate("/sources");
        }, 2000);
      } else {
        setError(status?.error_message || "Repository processing failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub upload failed");
    } finally {
      setUploading(false);
      setUploadProgress(null);
      setUploadedCount(0);
    }
  };

  const performUpload = async () => {
    setUploading(true);
    setError(null);
    setSuccess(null);
    setUploadProgress(null);

    try {
      // Generate a name from title or date if not provided
      const uploadName =
        title || `Upload ${new Date().toISOString().split("T")[0]}`;

      // Upload files in batches to avoid server limits
      if (selectedFiles.length > 0) {
        const fileCount = selectedFiles.length;
        const dirCount = directoryStructure.size;
        
        let totalProcessedFiles = 0;
        let totalSnippetsExtracted = 0;
        let jobIds = [];

        // Show initial upload progress
        if (dirCount > 0) {
          setUploadProgress(
            `Uploading ${fileCount} files from ${dirCount} ${dirCount === 1 ? "directory" : "directories"}...`,
          );
        } else {
          setUploadProgress(
            `Uploading ${fileCount} ${fileCount === 1 ? "file" : "files"}...`,
          );
        }

        // Process files in batches
        for (let i = 0; i < selectedFiles.length; i += batchSize) {
          const batch = selectedFiles.slice(i, Math.min(i + batchSize, selectedFiles.length));
          const batchNumber = Math.floor(i / batchSize) + 1;
          const totalBatches = Math.ceil(selectedFiles.length / batchSize);
          
          setUploadProgress(
            `Uploading batch ${batchNumber}/${totalBatches} (${batch.length} files)...`
          );

          // Upload this batch
          const result = await uploadFiles(
            batch,
            uploadName,
            title || undefined,
            version || undefined,
            typeof maxConcurrent === 'number' ? maxConcurrent : 10,
          );

          jobIds.push(result.job_id);
          
          // Poll for this batch's status
          let status = null;
          while (status?.status !== "completed" && status?.status !== "failed") {
            await new Promise((resolve) => setTimeout(resolve, 2000));
            status = await getUploadStatus(result.job_id);

            if (status.processed_files > 0) {
              setUploadProgress(
                `Batch ${batchNumber}/${totalBatches}: Processing ${status.processed_files}/${batch.length} files...`,
              );
              setUploadedCount(totalProcessedFiles + status.processed_files);
            }

            if (status.status === "completed" || status.status === "failed") {
              break;
            }
          }

          if (status.status === "completed") {
            totalProcessedFiles += status.processed_files;
            totalSnippetsExtracted += status.snippets_extracted;
          } else {
            setError(`Batch ${batchNumber} failed: ${status.error_message || "File processing failed"}`);
            return;
          }
        }

        // All batches completed successfully
        setSuccess(
          `Successfully processed ${totalProcessedFiles} files with ${totalSnippetsExtracted} code snippets extracted`,
        );
        setTimeout(() => {
          navigate("/sources");
        }, 2000);
      }

      // Upload pasted content if any (this remains synchronous for now)
      if (!selectedFiles.length && pastedContent.trim()) {
        const result = await uploadMarkdown({
          content: pastedContent,
          name: uploadName,
          title: title || "Pasted Content",
        });
        setSuccess(
          `Successfully uploaded content with ${result.snippets_count} code snippets extracted`,
        );
        setTimeout(() => {
          navigate("/sources");
        }, 2000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      setUploadProgress(null);
      setUploadedCount(0);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (activeTab === "github") {
      // Validate GitHub input
      if (!repoUrl) {
        setError("Please enter a GitHub repository URL");
        return;
      }

      // Generate a name from title or repo URL if not provided
      const uploadName =
        title ||
        (() => {
          const match = repoUrl.match(/\/([^/]+?)(?:\.git)?$/);
          return match ? match[1] : "Repository Documentation";
        })();

      // Check if a source with this name and version already exists
      const hasExisting = await checkForExistingSource(uploadName, version || undefined);

      if (hasExisting) {
        // Store the upload function to execute after confirmation
        setPendingUpload(() => performGitHubUpload);
        setShowConfirmDialog(true);
      } else {
        // No existing source, proceed directly
        await performGitHubUpload();
      }
    } else {
      // File upload
      if (selectedFiles.length === 0 && !pastedContent.trim()) {
        setError("Please select files to upload or paste content");
        return;
      }

      // Generate a name from title or date if not provided
      const uploadName =
        title || `Upload ${new Date().toISOString().split("T")[0]}`;

      // Check if a source with this name and version already exists
      const hasExisting = await checkForExistingSource(uploadName, version || undefined);

      if (hasExisting) {
        // Store the upload function to execute after confirmation
        setPendingUpload(() => performUpload);
        setShowConfirmDialog(true);
      } else {
        // No existing source, proceed directly
        await performUpload();
      }
    }
  };

  const handleConfirmUpload = async () => {
    setShowConfirmDialog(false);
    if (pendingUpload) {
      await pendingUpload();
    }
  };

  const handleCancelUpload = () => {
    setShowConfirmDialog(false);
    setExistingSourceInfo(null);
    setPendingUpload(null);
  };

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  };

  return (
    <div className="space-y-6 mb-8">
      <div>
        <h1 className="text-3xl font-bold">Upload Documentation</h1>
        <p className="mt-2 text-muted-foreground">
          Upload markdown files or clone GitHub repositories to extract code
          snippets
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("files")}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === "files"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <div className="flex items-center gap-2">
              <FileCode className="h-4 w-4" />
              Files Upload
            </div>
          </button>
          <button
            onClick={() => setActiveTab("github")}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === "github"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <div className="flex items-center gap-2">
              <Github className="h-4 w-4" />
              GitHub Repository
            </div>
          </button>
        </nav>
      </div>
      {/* Upload Progress */}
      {uploadProgress && (
        <div className="rounded-md bg-blue-50 p-4">
          <div className="flex items-center">
            <Loader2 className="animate-spin h-5 w-5 text-blue-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-blue-800">
                {uploadProgress}
              </p>
              {uploadedCount > 0 && (
                <p className="text-xs text-blue-600 mt-1">
                  Processed: {uploadedCount} files
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="rounded-md bg-green-50 p-4">
          <div className="flex">
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">{success}</p>
            </div>
          </div>
        </div>
      )}

      <form 
  onSubmit={handleSubmit} 
  className="space-y-6 mb-20"
        >
        {/* Sticky Upload Header */}
        <div className="sticky top-0 z-10 bg-background border-b border-border py-4 -mx-6 px-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <h2 className="text-lg font-semibold">
                  {activeTab === "files" ? "Files Upload" : "GitHub Repository"}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {activeTab === "files" 
                    ? `${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''} selected`
                    : "Configure repository settings"
                  }
                </p>
              </div>
              {/* Back to top button - only visible when scrolled */}
              {showBackToTop && (
                <button
                  type="button"
                  onClick={scrollToTop}
                  className="p-2 text-black hover:text-foreground bg-gray-100 transition-colors rounded-md hover:bg-secondary"
                  title="Back to top"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              )}
            </div>
            <button
              type="submit"
              disabled={
                !configLoaded ||
                uploading ||
                checkingSource ||
                (activeTab === "files" &&
                  selectedFiles.length === 0 &&
                  !pastedContent.trim()) ||
                (activeTab === "github" && !repoUrl)
              }
              className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="animate-spin h-4 w-4" />
                  {activeTab === "github" ? "Processing..." : "Uploading..."}
                </>
              ) : checkingSource ? (
                <>
                  <Loader2 className="animate-spin h-4 w-4" />
                  Checking...
                </>
              ) : (
                <>
                  {activeTab === "github" ? (
                    <>
                      <Github className="h-4 w-4" />
                      Process Repository
                    </>
                  ) : (
                    <>
                      <UploadIcon className="h-4 w-4" />
                      Upload Files
                    </>
                  )}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Title Input - Common for both tabs */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium">
            Collection Name{" "}
            <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={
              activeTab === "github"
                ? "Name for this repository documentation"
                : "Name for this upload collection"
            }
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            {activeTab === "github"
              ? "Give your repository documentation a collection name (defaults to repo name)"
              : "Give your uploaded files a collection name for easier organization"}
          </p>
        </div>

        {/* Version Input - Common for both tabs */}
        <div>
          <label htmlFor="version" className="block text-sm font-medium">
            Version{" "}
            <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="text"
            id="version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="v1.0.0 or latest"
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            Specify a version to maintain multiple versions of the same documentation
          </p>
        </div>

        {/* Concurrent Files Input - Common for both tabs */}
        <div>
          <label htmlFor="maxConcurrent" className="block text-sm font-medium">
            Concurrent File Processing{" "}
            <span className="text-muted-foreground text-xs">(advanced)</span>
          </label>
          <input
            type="number"
            id="maxConcurrent"
            min="1"
            max="50"
            value={maxConcurrent}
            onChange={(e) => {
              const inputValue = e.target.value;
              
              // Allow empty string for user to clear and type
              if (inputValue === '') {
                setMaxConcurrent('');
                return;
              }
              
              const value = parseInt(inputValue);
              if (!isNaN(value)) {
                // Clamp value between 1 and 50
                if (value < 1) {
                  setMaxConcurrent(1);
                } else if (value > 50) {
                  setMaxConcurrent(50);
                } else {
                  setMaxConcurrent(value);
                }
              }
            }}
            onBlur={() => {
              // On blur, if empty or invalid, set to default
              if (maxConcurrent === '' || typeof maxConcurrent === 'string') {
                setMaxConcurrent(10);
              }
            }}
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            Number of files to process simultaneously. Higher values speed up processing but use more resources (default: 10)
          </p>
        </div>

        {/* Conditional Content based on active tab */}
        {activeTab === "files" ? (
          <>
            {/* File Upload / Drag & Drop */}
            <div>
              <label className="block text-sm font-medium mb-2">
                Upload Files
              </label>

              <div
                className={`relative border-2 border-dashed rounded-lg p-6 ${
                  isDragging ? "border-primary bg-primary/5" : "border-border"
                }`}
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <div className="text-center">
                  <UploadIcon className="mx-auto h-12 w-12 text-muted-foreground" />
                  <div className="mt-2">
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <span className="text-primary hover:text-primary/80">
                        Choose files
                      </span>
                      <input
                        id="file-upload"
                        name="file-upload"
                        type="file"
                        className="sr-only"
                        accept=".md,.txt,.markdown,.html,.htm,text/markdown,text/plain,text/html"
                        onChange={handleFileSelect}
                        multiple
                        disabled={!configLoaded}
                      />
                    </label>
                    <span className="text-muted-foreground"> or </span>
                    <label htmlFor="dir-upload" className="cursor-pointer">
                      <span className="text-primary hover:text-primary/80">
                        choose directory
                      </span>
                      <input
                        id="dir-upload"
                        name="dir-upload"
                        type="file"
                        className="sr-only"
                        {...{ webkitdirectory: "" } as any}
                        multiple
                        onChange={handleDirectorySelect}
                        disabled={!configLoaded}
                      />
                    </label>
                    <span className="text-muted-foreground">
                      {" "}
                      or drag and drop
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Markdown (.md, .markdown), HTML (.html, .htm), or text (.txt) files
                  </p>
                </div>
              </div>

              {/* Selected Files List */}
              {selectedFiles.length > 0 && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">
                        Selected files ({selectedFiles.length}):
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Total size:{" "}
                        {formatFileSize(
                          selectedFiles.reduce((sum, f) => sum + f.size, 0),
                        )}{" "}
                        / {formatFileSize(maxTotalSize)}
                      </p>
                    </div>
                    {selectedFiles.length > 1 && (
                      <button
                        type="button"
                        onClick={clearAllFiles}
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        Clear all
                      </button>
                    )}
                  </div>

                  {/* Show directory structure if files are from directory upload */}
                  {directoryStructure.size > 0 ? (
                    <div className="space-y-2">
                      {Array.from(directoryStructure.entries()).map(
                        ([dir, files]) => (
                          <div
                            key={dir}
                            className="border border-border rounded-md p-2"
                          >
                            <div className="flex items-center space-x-2 mb-1">
                              <Folder className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm font-medium">
                                {dir === "/" ? "Root" : dir}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                ({files.length} files)
                              </span>
                            </div>
                            <div className="ml-6 space-y-1">
                              {files.map((file, fileIndex) => {
                                const globalIndex = selectedFiles.indexOf(file);
                                return (
                                  <div
                                    key={fileIndex}
                                    className="flex items-center justify-between p-1 bg-secondary rounded-md"
                                  >
                                    <div className="flex items-center space-x-2">
                                      <FileCode className="h-3 w-3 text-muted-foreground" />
                                      <span className="text-xs">
                                        {file.name}
                                      </span>
                                      <span className="text-xs text-muted-foreground">
                                        ({formatFileSize(file.size)})
                                      </span>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => removeFile(globalIndex)}
                                      className="text-muted-foreground hover:text-foreground"
                                    >
                                      <X className="h-3 w-3" />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {selectedFiles.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-2 bg-secondary rounded-md"
                        >
                          <div className="flex items-center space-x-2">
                            <FileCode className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">{file.name}</span>
                            <span className="text-xs text-muted-foreground">
                              ({formatFileSize(file.size)})
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Manual Content Input */}
            <div>
              <label htmlFor="content" className="block text-sm font-medium">
                Or Paste Content Directly
              </label>
              <textarea
                id="content"
                rows={10}
                value={pastedContent}
                onChange={(e) => setPastedContent(e.target.value)}
                placeholder="Paste your markdown content here..."
                className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary font-mono"
              />
              <p className="mt-1 text-sm text-muted-foreground">
                Paste markdown or code directly for quick uploads without
                creating a file
              </p>
            </div>
          </>
        ) : (
          <>
            {/* GitHub Repository Form */}
            <div className="space-y-4">
              <div>
                <label htmlFor="repo-url" className="block text-sm font-medium">
                  Repository URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  id="repo-url"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/user/repository"
                  className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <p className="mt-1 text-sm text-muted-foreground">
                  Enter the GitHub repository URL containing markdown
                  documentation
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="repo-path"
                    className="block text-sm font-medium"
                  >
                    Path within Repository
                  </label>
                  <input
                    type="text"
                    id="repo-path"
                    value={repoPath}
                    onChange={(e) => setRepoPath(e.target.value)}
                    placeholder="docs (optional)"
                    className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Process only this folder
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="repo-branch"
                    className="block text-sm font-medium"
                  >
                    Branch
                  </label>
                  <input
                    type="text"
                    id="repo-branch"
                    value={repoBranch}
                    onChange={(e) => setRepoBranch(e.target.value)}
                    placeholder="main"
                    className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Git branch to clone
                  </p>
                </div>
              </div>

              <div>
                <label
                  htmlFor="repo-token"
                  className="block text-sm font-medium"
                >
                  Access Token
                </label>
                <input
                  type="password"
                  id="repo-token"
                  value={repoToken}
                  onChange={(e) => setRepoToken(e.target.value)}
                  placeholder="ghp_... (for private repos)"
                  className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <p className="mt-1 text-sm text-muted-foreground">
                  GitHub personal access token for private repositories
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="repo-include"
                    className="block text-sm font-medium"
                  >
                    Include Patterns
                  </label>
                  <input
                    type="text"
                    id="repo-include"
                    value={repoIncludePatterns}
                    onChange={(e) => setRepoIncludePatterns(e.target.value)}
                    placeholder="docs/**/*.md, examples/**/*.md"
                    className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Comma-separated file patterns to include
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="repo-exclude"
                    className="block text-sm font-medium"
                  >
                    Exclude Patterns
                  </label>
                  <input
                    type="text"
                    id="repo-exclude"
                    value={repoExcludePatterns}
                    onChange={(e) => setRepoExcludePatterns(e.target.value)}
                    placeholder="**/test/*.md, **/node_modules/**"
                    className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Comma-separated file patterns to exclude
                  </p>
                </div>
              </div>

              {/* GitHub Info Box */}
              <div className="rounded-md bg-blue-50 dark:bg-blue-900/20 p-4">
                <div className="flex">
                  <GitBranch className="h-5 w-5 text-blue-400 mt-0.5" />
                  <div className="ml-3 text-sm">
                    <p className="font-medium text-blue-800 dark:text-blue-200">
                      Repository Processing
                    </p>
                    <ul className="mt-1 text-blue-700 dark:text-blue-300 space-y-1">
                      <li>• The repository will be cloned temporarily</li>
                      <li>• Only markdown files will be processed</li>
                      <li>
                        • Files are automatically cleaned up after processing
                      </li>
                      <li>• Source URLs will link back to GitHub</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Upload Progress */}
        {uploadProgress && (
          <div className="rounded-md bg-blue-50 p-4 mb-10">
            <div className="flex items-center">
              <Loader2 className="animate-spin h-5 w-5 text-blue-400" />
              <div className="ml-3">
                <p className="text-sm font-medium text-blue-800">
                  {uploadProgress}
                </p>
                {uploadedCount > 0 && (
                  <p className="text-xs text-blue-600 mt-1">
                    Processed: {uploadedCount} files
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <div className="flex">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <p className="text-sm font-medium text-red-800">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Success Message */}
        {success && (
          <div className="rounded-md bg-green-50 p-4">
            <div className="flex">
              <CheckCircle2 className="h-5 w-5 text-green-400" />
              <div className="ml-3">
                <p className="text-sm font-medium text-green-800">{success}</p>
              </div>
            </div>
          </div>
        )}
      </form>

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showConfirmDialog}
        title="Add to Existing Source?"
        message={`A source named "${existingSourceInfo?.name}"${existingSourceInfo?.version ? ` (version ${existingSourceInfo.version})` : ''} already exists with ${existingSourceInfo?.documentCount} documents and ${existingSourceInfo?.snippetCount} code snippets. 

Your new files will be added to this existing source${existingSourceInfo?.version ? ' version' : ''}, allowing you to build a comprehensive documentation library in one place.

Would you like to continue adding to this source?`}
        confirmText="Yes, Add to Existing Source"
        cancelText="Cancel Upload"
        onConfirm={handleConfirmUpload}
        onCancel={handleCancelUpload}
        variant="default"
      />
    </div>
  );
}
