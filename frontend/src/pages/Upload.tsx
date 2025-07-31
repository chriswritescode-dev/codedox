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
  const [name, setName] = useState('')
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
    
    if (!name.trim()) {
      setError('Please provide a name for this upload')
      return
    }
    
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
        const result = await uploadFiles(selectedFiles, name, title || undefined)
        jobId = result.job_id
        uploadMessage = result.message
      }
      
      // Upload pasted content if any
      if (pastedContent.trim()) {
        const result = await uploadMarkdown({
          content: pastedContent,
          name,
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
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-100 mb-2">Upload Documentation</h1>
        <p className="text-gray-400 mb-8">Upload markdown files or paste content to extract code snippets</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
                Name *
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., My Documentation"
                required
              />
            </div>
            
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-300 mb-2">
                Title (Optional)
              </label>
              <input
                type="text"
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Document title"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Upload Files
            </label>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-gray-700 hover:border-gray-600'
              }`}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="file-upload"
                className="hidden"
                onChange={handleFileSelect}
                accept=".md,.markdown,.txt,text/markdown,text/plain"
                multiple
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer inline-flex flex-col items-center"
              >
                <UploadIcon className="w-12 h-12 text-gray-400 mb-4" />
                <span className="text-gray-300">
                  Drop files here or <span className="text-blue-400">browse</span>
                </span>
                <span className="text-sm text-gray-500 mt-2">
                  Supports .md, .markdown, and .txt files
                </span>
              </label>
            </div>
            
            {selectedFiles.length > 0 && (
              <div className="mt-4 space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FileCode className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="text-sm text-gray-300">{file.name}</p>
                        <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="text-gray-400 hover:text-gray-300"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="content" className="block text-sm font-medium text-gray-300 mb-2">
              Or Paste Content
            </label>
            <textarea
              id="content"
              value={pastedContent}
              onChange={(e) => setPastedContent(e.target.value)}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              rows={10}
              placeholder="Paste your markdown content here..."
            />
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-red-400 bg-red-400/10 p-4 rounded-lg">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center space-x-2 text-green-400 bg-green-400/10 p-4 rounded-lg">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          <div className="flex justify-end space-x-4">
            <button
              type="button"
              onClick={() => navigate('/sources')}
              className="px-6 py-2 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-900 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading || (!selectedFiles.length && !pastedContent.trim())}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-800 text-white rounded-lg transition-colors flex items-center space-x-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <FileText className="w-5 h-5" />
                  <span>Upload</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}