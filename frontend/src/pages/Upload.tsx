import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload as UploadIcon,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  FileCode,
  Folder,
} from "lucide-react";
import { uploadMarkdown, uploadFiles, api } from '../lib/api'
import { ConfirmationDialog } from '../components/ConfirmationDialog'

const MAX_TOTAL_SIZE = 500 * 1024 * 1024 // 500MB total size limit
const BATCH_SIZE = 100 // Upload files in batches of 100

export default function Upload() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);
  
  const [title, setTitle] = useState('')
  const [pastedContent, setPastedContent] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [directoryStructure, setDirectoryStructure] = useState<
    Map<string, File[]>
  >(new Map());
  
  // Confirmation dialog state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [existingSourceInfo, setExistingSourceInfo] = useState<{
    name: string
    snippetCount: number
    documentCount: number
  } | null>(null)
  const [pendingUpload, setPendingUpload] = useState<(() => Promise<void>) | null>(null)
  const [checkingSource, setCheckingSource] = useState(false)

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    
    const files = Array.from(e.dataTransfer.files)
    const validFiles = files.filter(file => 
      file.type === 'text/markdown' || 
      file.type === 'text/plain' || 
      file.name.endsWith('.md') ||
      file.name.endsWith('.txt') ||
      file.name.endsWith('.markdown')
    )
    
    if (validFiles.length > 0) {
      // Check total size limit
      const currentSize = selectedFiles.reduce((sum, f) => sum + f.size, 0)
      const newSize = validFiles.reduce((sum, f) => sum + f.size, 0)
      const totalSize = currentSize + newSize
      if (totalSize > MAX_TOTAL_SIZE) {
        setError(`Total file size exceeds ${formatFileSize(MAX_TOTAL_SIZE)} limit. Current total: ${formatFileSize(totalSize)}`)
        return
      }
      
      setSelectedFiles(prev => [...prev, ...validFiles])
      if (!title && validFiles.length === 1) {
        setTitle(validFiles[0].name.replace(/\.(md|txt|markdown)$/, ''))
      }
    } else {
      setError('Please upload markdown (.md, .markdown) or text (.txt) files')
    }
  }, [title])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const validFiles = Array.from(files).filter(file => 
        file.type === 'text/markdown' || 
        file.type === 'text/plain' || 
        file.name.endsWith('.md') ||
        file.name.endsWith('.txt') ||
        file.name.endsWith('.markdown')
      )
      
      if (validFiles.length > 0) {
        // Check total size limit
        const currentSize = selectedFiles.reduce((sum, f) => sum + f.size, 0)
        const newSize = validFiles.reduce((sum, f) => sum + f.size, 0)
        const totalSize = currentSize + newSize
        if (totalSize > MAX_TOTAL_SIZE) {
          setError(`Total file size exceeds ${formatFileSize(MAX_TOTAL_SIZE)} limit. Current total: ${formatFileSize(totalSize)}`)
          return
        }
        
        setSelectedFiles(prev => [...prev, ...validFiles])
        // Set title from first file if not already set
        if (!title && validFiles.length === 1) {
          setTitle(validFiles[0].name.replace(/\.(md|txt|markdown)$/, ''))
        }
      } else {
        setError('Please upload markdown (.md, .markdown) or text (.txt) files')
      }
    }
  }
  
  const handleDirectorySelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const fileArray = Array.from(files);
      const validFiles = fileArray.filter(
        (file) =>
          file.name.endsWith(".md") ||
          file.name.endsWith(".txt") ||
          file.name.endsWith(".markdown"),
      );

      if (validFiles.length > 0) {
        // Check total size limit
        const currentSize = selectedFiles.reduce((sum, f) => sum + f.size, 0)
        const newSize = validFiles.reduce((sum, f) => sum + f.size, 0)
        const totalSize = currentSize + newSize
        if (totalSize > MAX_TOTAL_SIZE) {
          setError(`Total file size exceeds ${formatFileSize(MAX_TOTAL_SIZE)} limit. Current total: ${formatFileSize(totalSize)}`)
          return
        }
        
        // Group files by directory
        const dirMap = new Map<string, File[]>();
        validFiles.forEach((file) => {
          // @ts-ignore - webkitRelativePath is not in the File type but exists
          const path = file.webkitRelativePath || file.name;
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
          // @ts-ignore
          const firstPath = validFiles[0].webkitRelativePath || "";
          const rootDir = firstPath.split("/")[0];
          if (rootDir) {
            setTitle(rootDir);
          }
        }
      } else {
        setError(
          "No markdown (.md, .markdown) or text (.txt) files found in the selected directory",
        );
      }
    }
  };
  
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }
  
  const clearAllFiles = () => {
    setSelectedFiles([]);
    setDirectoryStructure(new Map());
  };
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const checkForExistingSource = async (name: string): Promise<boolean> => {
    setCheckingSource(true)
    try {
      const result = await api.searchSources({ query: name, limit: 100 })
      // Look for exact match (case-insensitive)
      const exactMatch = result.sources.find(
        source => source.name.toLowerCase() === name.toLowerCase()
      )
      
      if (exactMatch) {
        setExistingSourceInfo({
          name: exactMatch.name,
          snippetCount: exactMatch.snippets_count || 0,
          documentCount: exactMatch.documents_count || 0
        })
        return true
      }
      return false
    } catch (error) {
      console.error('Error checking for existing source:', error)
      // If we can't check, proceed without confirmation
      return false
    } finally {
      setCheckingSource(false)
    }
  }

  const performUpload = async () => {
    setUploading(true)
    setError(null)
    setSuccess(null)
    setUploadProgress(null);
    
    try {
      let jobId = null
      let uploadMessage = ''
      
      // Generate a name from title or date if not provided
      const uploadName = title || `Upload ${new Date().toISOString().split('T')[0]}`
      
      // Upload files in batches
      if (selectedFiles.length > 0) {
        const fileCount = selectedFiles.length;
        const dirCount = directoryStructure.size;
        const batches = Math.ceil(fileCount / BATCH_SIZE);
        
        let totalSnippets = 0;
        let processedFiles = 0;
        
        for (let i = 0; i < batches; i++) {
          const start = i * BATCH_SIZE;
          const end = Math.min(start + BATCH_SIZE, fileCount);
          const batch = selectedFiles.slice(start, end);
          
          // Update progress
          if (batches > 1) {
            setUploadProgress(
              `Uploading batch ${i + 1}/${batches} (files ${start + 1}-${end} of ${fileCount})...`
            );
          } else if (dirCount > 0) {
            setUploadProgress(
              `Uploading ${fileCount} files from ${dirCount} ${dirCount === 1 ? "directory" : "directories"}...`
            );
          } else {
            setUploadProgress(
              `Uploading ${fileCount} ${fileCount === 1 ? "file" : "files"}...`
            );
          }
          
          try {
            const result = await uploadFiles(batch, uploadName, title || undefined);
            jobId = result.job_id;
            processedFiles += result.file_count;
            totalSnippets += parseInt(result.message.match(/\d+(?= code snippets)/)?.[0] || '0');
            setUploadedCount(processedFiles);
          } catch (err) {
            // If a batch fails, show which batch failed
            const errorMsg = err instanceof Error ? err.message : 'Upload failed';
            throw new Error(`Batch ${i + 1}/${batches} failed: ${errorMsg}`);
          }
        }
        
        uploadMessage = `Successfully processed ${processedFiles} files with ${totalSnippets} code snippets extracted`;
      }
      
      // Upload pasted content if any
      if (pastedContent.trim()) {
        const result = await uploadMarkdown({
          content: pastedContent,
          name: uploadName,
          title: title || 'Pasted Content'
        })
        if (jobId) {
          uploadMessage += ` and pasted content with ${result.snippets_count} snippets`
        } else {
          uploadMessage = `Successfully uploaded content with ${result.snippets_count} code snippets extracted`
        }
      }
      
      setSuccess(uploadMessage)
      setUploadProgress(null);
      
      // Clear form after successful upload
      setTimeout(() => {
        navigate('/sources')
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      setUploadProgress(null);
      setUploadedCount(0);
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (selectedFiles.length === 0 && !pastedContent.trim()) {
      setError('Please select files to upload or paste content')
      return
    }
    
    // Generate a name from title or date if not provided
    const uploadName = title || `Upload ${new Date().toISOString().split('T')[0]}`
    
    // Check if a source with this name already exists
    const hasExisting = await checkForExistingSource(uploadName)
    
    if (hasExisting) {
      // Store the upload function to execute after confirmation
      setPendingUpload(() => performUpload)
      setShowConfirmDialog(true)
    } else {
      // No existing source, proceed directly
      await performUpload()
    }
  }
  
  const handleConfirmUpload = async () => {
    setShowConfirmDialog(false)
    if (pendingUpload) {
      await pendingUpload()
    }
  }
  
  const handleCancelUpload = () => {
    setShowConfirmDialog(false)
    setExistingSourceInfo(null)
    setPendingUpload(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Upload Documentation</h1>
        <p className="mt-2 text-muted-foreground">
          Upload markdown or text files to extract code snippets with AI
        </p>
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

      <form onSubmit={handleSubmit} className="space-y-6 mb-20">
        {/* Title Input */}
        <div className="flex items-center gap-4">
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
              placeholder="Name for this upload collection"
              className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="mt-1 text-sm text-muted-foreground">
              Give your uploaded files a collection name for easier organization
            </p>
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={
                uploading ||
                (selectedFiles.length === 0 && !pastedContent.trim())
              }
              className="flex items-center justify-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
                  Uploading...
                </>
              ) : (
                <>
                  <UploadIcon className="-ml-1 mr-2 h-4 w-4" />
                  Upload
                </>
              )}
            </button>
          </div>
        </div>

        {/* File Upload / Drag & Drop */}
        <div>
          <label className="block text-sm font-medium mb-2">Upload Files</label>

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
                    accept=".md,.txt,.markdown,text/markdown,text/plain"
                    onChange={handleFileSelect}
                    multiple
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
                    // @ts-ignore - webkitdirectory is not in the type but works
                    webkitdirectory=""
                    directory=""
                    multiple
                    onChange={handleDirectorySelect}
                  />
                </label>
                <span className="text-muted-foreground"> or drag and drop</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Markdown (.md, .markdown) or text (.txt) files
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
                    / {formatFileSize(MAX_TOTAL_SIZE)}
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
                                  <span className="text-xs">{file.name}</span>
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
            Paste markdown or code directly for quick uploads without creating a
            file
          </p>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={uploading || checkingSource || (selectedFiles.length === 0 && !pastedContent.trim())}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="animate-spin h-4 w-4" />
                Uploading...
              </>
            ) : checkingSource ? (
              <>
                <Loader2 className="animate-spin h-4 w-4" />
                Checking...
              </>
            ) : (
              'Upload Files'
            )}
          </button>
        </div>
      </form>
      
      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showConfirmDialog}
        title="Add to Existing Source?"
        message={`A source named "${existingSourceInfo?.name}" already exists with ${existingSourceInfo?.documentCount} documents and ${existingSourceInfo?.snippetCount} code snippets. 

Your new files will be added to this existing source, allowing you to build a comprehensive documentation library in one place.

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
