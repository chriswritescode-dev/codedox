import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, AlertCircle, CheckCircle2, Loader2, X } from 'lucide-react'
import { uploadMarkdown, uploadFile } from '../lib/api'

export default function Upload() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Form fields
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
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
      file.type === 'text/markdown' || file.type === 'text/plain' || file.name.endsWith('.md') || file.name.endsWith('.txt')
    )
    
    if (validFiles.length > 0) {
      setSelectedFiles(prev => [...prev, ...validFiles])
    } else if (files.length > 0) {
      setError('Please upload markdown (.md) or text (.txt) files')
    }
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const validFiles = Array.from(files).filter(file =>
        file.type === 'text/markdown' || file.type === 'text/plain' || file.name.endsWith('.md') || file.name.endsWith('.txt')
      )
      
      if (validFiles.length > 0) {
        setSelectedFiles(prev => [...prev, ...validFiles])
      } else {
        setError('Please upload markdown (.md) or text (.txt) files')
      }
    }
  }
  
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      setError('Please provide a name for this upload')
      return
    }
    
    if (selectedFiles.length === 0 && !content.trim()) {
      setError('Please select files or provide content to upload')
      return
    }
    
    setUploading(true)
    setError(null)
    setSuccess(null)
    
    try {
      let totalSnippets = 0
      let uploadedCount = 0
      
      // Upload each file
      for (const file of selectedFiles) {
        const result = await uploadFile(file, name, title)
        totalSnippets += result.snippets_count
        uploadedCount++
      }
      
      // Upload pasted content if any
      if (content.trim()) {
        const result = await uploadMarkdown({
          content,
          name,
          title: title || 'Pasted Content'
        })
        totalSnippets += result.snippets_count
        uploadedCount++
      }
      
      setSuccess(`Successfully uploaded ${uploadedCount} item(s) with ${totalSnippets} total code snippets extracted`)
      
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
        {/* Name Input */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium">
            Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., React Hooks Documentation"
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
            required
          />
          <p className="mt-1 text-sm text-muted-foreground">
            A descriptive name for this documentation upload
          </p>
        </div>

        {/* Title Input */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium">
            Title
          </label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Optional title for the document"
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* File Upload / Drag & Drop */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Content <span className="text-red-500">*</span>
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
                  <span className="text-primary hover:text-primary/80">Upload a file</span>
                  <input
                    id="file-upload"
                    name="file-upload"
                    type="file"
                    className="sr-only"
                    accept=".md,.txt,text/markdown,text/plain"
                    onChange={handleFileSelect}
                    multiple
                  />
                </label>
                <span className="text-muted-foreground"> or drag and drop</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Multiple markdown or text files up to 10MB each</p>
            </div>
            
            {selectedFiles.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-sm font-medium text-center">Selected Files:</p>
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between bg-secondary/50 rounded px-3 py-2">
                    <div className="flex items-center space-x-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{file.name}</span>
                      <span className="text-xs text-muted-foreground">({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Manual Content Input */}
        <div>
          <label htmlFor="content" className="block text-sm font-medium">
            Or paste content directly
          </label>
          <textarea
            id="content"
            rows={10}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your markdown content here..."
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary font-mono"
          />
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
            disabled={uploading || !name.trim() || (selectedFiles.length === 0 && !content.trim())}
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