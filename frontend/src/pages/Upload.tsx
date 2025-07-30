import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, AlertCircle, CheckCircle2, Loader2, X, FileCode } from 'lucide-react'
import { uploadMarkdown, uploadFiles } from '../lib/api'

export default function Upload() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Form fields
  const [title, setTitle] = useState('')
  const [pastedContent, setPastedContent] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

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
      setSelectedFiles(prev => [...prev, ...validFiles])
      // Set title from first file if not already set
      if (!title && validFiles.length === 1) {
        setTitle(validFiles[0].name.replace(/\.(md|txt|markdown)$/, ''))
      }
    } else {
      setError('Please upload markdown (.md, .markdown) or text (.txt) files')
    }
  }, [])

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
        setSelectedFiles(prev => [...prev, ...validFiles])
        // Set title from first file if not already set
        if (!title && validFiles.length === 1) {
          setTitle(validFiles[0].name.replace(/\.(md|txt|markdown)$/, ''))
        }
      }
    }
  }
  
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (selectedFiles.length === 0 && !pastedContent.trim()) {
      setError('Please select files to upload or paste content')
      return
    }
    
    setUploading(true)
    setError(null)
    setSuccess(null)
    
    try {
      let jobId = null
      let uploadMessage = ''
      
      // Upload files using batch endpoint
      if (selectedFiles.length > 0) {
        const result = await uploadFiles(selectedFiles, title || undefined)
        jobId = result.job_id
        uploadMessage = result.message
      }
      
      // Upload pasted content if any
      if (pastedContent.trim()) {
        const result = await uploadMarkdown({
          content: pastedContent,
          title: title || 'Pasted Content'
        })
        if (jobId) {
          uploadMessage += ` and pasted content with ${result.snippets_count} snippets`
        } else {
          uploadMessage = `Successfully uploaded content with ${result.snippets_count} code snippets extracted`
        }
      }
      
      setSuccess(uploadMessage)
      
      // Clear form after successful upload
      setTimeout(() => {
        navigate('/sources')
      }, 2000)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload content'
      setError(message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Upload Documentation</h1>
        <p className="mt-2 text-muted-foreground">
          Upload markdown or text files to extract code snippets with AI
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Title Input */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium">
            Collection Name <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Name for this upload collection"
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            Give your uploaded files a collection name for easier organization
          </p>
        </div>

        {/* File Upload / Drag & Drop */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Upload Files
          </label>
          
          <div
            className={`relative border-2 border-dashed rounded-lg p-6 ${
              isDragging ? 'border-primary bg-primary/5' : 'border-border'
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
                  <span className="text-primary hover:text-primary/80">Choose files</span>
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
                <span className="text-muted-foreground"> or drag and drop</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Markdown (.md, .markdown) or text (.txt) files</p>
            </div>
          </div>
          
          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-sm font-medium">Selected files ({selectedFiles.length}):</p>
              <div className="space-y-1">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-secondary rounded-md">
                    <div className="flex items-center space-x-2">
                      <FileCode className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{file.name}</span>
                      <span className="text-xs text-muted-foreground">({formatFileSize(file.size)})</span>
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
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary font-mono"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            Paste markdown or code directly for quick uploads without creating a file
          </p>
        </div>

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

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={uploading || (selectedFiles.length === 0 && !pastedContent.trim())}
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
      </form>
    </div>
  )
}