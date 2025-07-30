import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { uploadMarkdown, uploadFile } from '../lib/api'

export default function Upload() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Form fields
  const [sourceUrl, setSourceUrl] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

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
    if (files.length > 0) {
      const file = files[0]
      if (file.type === 'text/markdown' || file.type === 'text/plain' || file.name.endsWith('.md')) {
        setSelectedFile(file)
        // Read file content
        const reader = new FileReader()
        reader.onload = (e) => {
          const text = e.target?.result as string
          setContent(text)
          setTitle(file.name.replace(/\.(md|txt)$/, ''))
        }
        reader.readAsText(file)
      } else {
        setError('Please upload a markdown (.md) or text (.txt) file')
      }
    }
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      const file = files[0]
      setSelectedFile(file)
      // Read file content
      const reader = new FileReader()
      reader.onload = (e) => {
        const text = e.target?.result as string
        setContent(text)
        setTitle(file.name.replace(/\.(md|txt)$/, ''))
      }
      reader.readAsText(file)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!content.trim()) {
      setError('Please provide content to upload')
      return
    }
    
    // Source URL is now optional
    
    setUploading(true)
    setError(null)
    setSuccess(null)
    
    try {
      if (selectedFile) {
        // Use file upload endpoint
        const result = await uploadFile(selectedFile, sourceUrl || undefined, title)
        setSuccess(`Successfully uploaded file with ${result.snippets_count} code snippets extracted`)
      } else {
        // Use markdown upload endpoint
        const result = await uploadMarkdown({
          content,
          source_url: sourceUrl || undefined,
          title: title || undefined
        })
        setSuccess(`Successfully uploaded content with ${result.snippets_count} code snippets extracted`)
      }
      
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
        {/* Source URL Input */}
        <div>
          <label htmlFor="source-url" className="block text-sm font-medium">
            Source URL <span className="text-muted-foreground text-xs">(optional)</span>
          </label>
          <input
            type="url"
            id="source-url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://docs.example.com/guide (optional)"
            className="mt-1 w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-hidden focus:ring-2 focus:ring-primary"
          />
          <p className="mt-1 text-sm text-muted-foreground">
            The original URL where this documentation can be found
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
                  />
                </label>
                <span className="text-muted-foreground"> or drag and drop</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Markdown or text files up to 10MB</p>
            </div>
            
            {selectedFile && (
              <div className="mt-4 flex items-center justify-center space-x-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                <span>{selectedFile.name}</span>
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
            disabled={uploading || !content.trim() || !sourceUrl.trim()}
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