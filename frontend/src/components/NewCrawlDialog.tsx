import React, { useState, useEffect, useMemo } from 'react';
import { X, Plus, RefreshCw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useToast } from '../hooks/useToast';
import { useKeyboardShortcut } from '../hooks/useKeyboardShortcut';
import { SourceAutocomplete } from './SourceAutocomplete';
import { ConfirmationDialog } from './ConfirmationDialog';
import { api, SourceOption } from '../lib/api';
import { useSources } from '../hooks/useSources';

type DialogMode = 'create' | 'update';

interface CrawlSubmitData {
  name?: string;
  version?: string;
  base_url: string;
  max_depth: number;
  max_pages?: number;
  domain_filter?: string;
  url_patterns?: string[];
  max_concurrent_crawls?: number;
  add_url_patterns?: string[];
  exclude_url_patterns?: string[];
}

interface PendingSubmit {
  submitData: CrawlSubmitData;
  mode: DialogMode;
  selectedSource?: SourceOption;
}

interface NewCrawlDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CrawlSubmitData, mode: DialogMode, selectedSource?: SourceOption) => void;
  isSubmitting?: boolean;
}

export const NewCrawlDialog: React.FC<NewCrawlDialogProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) => {
  const toast = useToast();
  const [mode, setMode] = useState<DialogMode>('create');
  const [selectedSource, setSelectedSource] = useState<SourceOption | null>(null);
  
  const shouldLoadSources = useMemo(() => isOpen && mode === 'update', [isOpen, mode]);
  const { sources, isLoading: isLoadingSources } = useSources(shouldLoadSources);
  
  const { data: sourceDetails } = useQuery({
    queryKey: ['source-details', selectedSource?.id],
    queryFn: () => api.getSource(selectedSource!.id),
    enabled: !!selectedSource && mode === 'update',
    staleTime: 5 * 60 * 1000,
  });
  
  const [formData, setFormData] = useState({
    name: '',
    version: '',
    base_url: '',
    max_depth: 1,
    max_pages: undefined as number | undefined,
    domain_filter: '',
    url_patterns: '',
    max_concurrent_crawls: 5,
    add_url_patterns: '',
    exclude_url_patterns: '',
  });
  
  const [maxConcurrentInput, setMaxConcurrentInput] = useState('5');
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingSubmit, setPendingSubmit] = useState<PendingSubmit | null>(null);

  useEffect(() => {
    if (sourceDetails && mode === 'update') {
      setFormData(prev => ({
        ...prev,
        name: sourceDetails.name,
        version: sourceDetails.version || '',
        base_url: sourceDetails.base_url,
      }));
    }
  }, [sourceDetails, mode]);

  const handleModeChange = (newMode: DialogMode) => {
    setMode(newMode);
    if (newMode === 'create') {
      setSelectedSource(null);
      // Reset form to defaults for create mode
      setFormData({
        name: '',
        version: '',
        base_url: '',
        max_depth: 1,
        max_pages: undefined,
        domain_filter: '',
        url_patterns: '',
        max_concurrent_crawls: 5,
        add_url_patterns: '',
        exclude_url_patterns: '',
      });
      setMaxConcurrentInput('5');
    }
  };

  const handleClose = () => {
    setFormData({ 
      name: '', 
      version: '', 
      base_url: '', 
      max_pages: undefined, 
      max_depth: 1, 
      domain_filter: '', 
      url_patterns: '', 
      max_concurrent_crawls: 5,
      add_url_patterns: '',
      exclude_url_patterns: '',
    });
    setMaxConcurrentInput('5');
    setSelectedSource(null);
    setMode('create');
    onClose();
  };

  // Handle Escape key to close dialog
  useKeyboardShortcut('Escape', handleClose, isOpen && !isSubmitting);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation for update mode
    if (mode === 'update' && !selectedSource) {
      toast.warning('Please select a source to update');
      return;
    }
    
    if (!formData.base_url) {
      toast.warning('Please enter a base URL');
      return;
    }

    // Use the current max_concurrent_crawls value, falling back to form data
    const finalMaxConcurrent = maxConcurrentInput ? parseInt(maxConcurrentInput) || formData.max_concurrent_crawls : formData.max_concurrent_crawls;
    
    const submitData = {
      ...formData,
      name: formData.name || undefined, // Allow empty name for auto-detection
      version: formData.version || undefined,
      max_pages: formData.max_pages || undefined,
      domain_filter: formData.domain_filter || undefined,
      url_patterns: formData.max_depth > 0 && formData.url_patterns 
        ? formData.url_patterns.split(',').map(p => p.trim()).filter(p => p)
        : undefined,
      max_concurrent_crawls: Math.max(0, Math.min(100, finalMaxConcurrent)), // Clamp between 0-100
      // Add update-specific fields
      add_url_patterns: mode === 'update' && formData.add_url_patterns
        ? formData.add_url_patterns.split(',').map(p => p.trim()).filter(p => p)
        : undefined,
      exclude_url_patterns: mode === 'update' && formData.exclude_url_patterns
        ? formData.exclude_url_patterns.split(',').map(p => p.trim()).filter(p => p)
        : undefined,
    };

    // Show confirmation dialog for update mode
    if (mode === 'update') {
      setPendingSubmit({ submitData, mode, selectedSource: selectedSource || undefined });
      setShowConfirmDialog(true);
    } else {
      onSubmit(submitData, mode, selectedSource || undefined);
    }
  };

  const handleConfirmSubmit = () => {
    if (pendingSubmit) {
      onSubmit(pendingSubmit.submitData, pendingSubmit.mode, pendingSubmit.selectedSource);
      setPendingSubmit(null);
    }
  };

  const handleCancelConfirm = () => {
    setPendingSubmit(null);
    setShowConfirmDialog(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-600/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-card border-2 border-border rounded-lg w-full max-w-2xl max-h-[90vh] shadow-2xl animate-slide-up flex flex-col">
        <div className="flex items-center justify-between p-6 pb-4 border-b border-border">
          <h2 className="text-xl font-semibold">
            {mode === 'create' ? 'Create New Crawl' : 'Update Existing Source'}
          </h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mode Selection */}
        <div className="px-6 py-4 border-b border-border">
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => handleModeChange('create')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-all ${
                mode === 'create'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              <Plus className="h-4 w-4" />
              Create New Source
            </button>
            <button
              type="button"
              onClick={() => handleModeChange('update')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-all ${
                mode === 'update'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
            >
              <RefreshCw className="h-4 w-4" />
              Update Existing Source
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            
            {/* Source Selection for Update Mode */}
            {mode === 'update' && (
              <div>
                <label htmlFor="source_select" className="block text-sm font-medium mb-1">
                  Select Source <span className="text-destructive">*</span>
                </label>
                <SourceAutocomplete
                  sources={sources}
                  selectedSource={selectedSource}
                  onSourceSelect={setSelectedSource}
                  placeholder="Search for a source to update..."
                  disabled={isSubmitting}
                  isLoading={isLoadingSources}
                />
                {selectedSource && (
                  <div className="mt-2 p-2 bg-secondary/50 rounded-md">
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium">Current Stats:</span> {selectedSource.documents_count} documents, {selectedSource.snippets_count} snippets
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Basic fields - shown in both modes but with different behavior */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1">
                Name <span className="text-xs text-muted-foreground">
                  {mode === 'create' ? '(optional - auto-detected if empty)' : '(source name)'}
                </span>
              </label>
              <input
                id="name"
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={mode === 'update' && !!selectedSource}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
                placeholder={mode === 'create' ? "Will be auto-detected from site (e.g., Next.js Documentation)" : "Source name"}
              />
            </div>

            {/* Version field - editable in both modes */}
            <div>
              <label htmlFor="version" className="block text-sm font-medium mb-1">
                Version <span className="text-xs text-muted-foreground">
                  {mode === 'create' ? '(optional - e.g., v14, v15, 2.0)' : '(current version, can be updated)'}
                </span>
              </label>
              <input
                id="version"
                type="text"
                value={formData.version}
                onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="e.g., v14, v15, 2.0"
              />
              <p className="text-xs text-muted-foreground mt-1">
                {mode === 'create' 
                  ? "Specify a version to differentiate multiple versions of the same library"
                  : "Update version for this crawl"
                }
              </p>
            </div>

            {/* Base URL - disabled in update mode */}
            <div>
              <label htmlFor="base_url" className="block text-sm font-medium mb-1">
                Base URL <span className="text-destructive">*</span>
                {mode === 'update' && <span className="text-xs text-muted-foreground ml-2">(cannot be changed)</span>}
              </label>
              <input
                id="base_url"
                type="url"
                value={formData.base_url}
                onChange={(e) => {
                  if (mode === 'create') {
                    const url = e.target.value;
                    setFormData((prev) => {
                      // Auto-populate domain filter when base URL changes
                      let domain = prev.domain_filter;
                      if (!prev.domain_filter && url) {
                        try {
                          const parsed = new URL(url);
                          domain = parsed.hostname;
                        } catch (err) {
                          // Invalid URL, keep existing domain
                        }
                      }
                      return { ...prev, base_url: url, domain_filter: domain };
                    });
                  }
                }}
                disabled={mode === 'update'}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
                placeholder="https://nextjs.org/docs"
                required
              />
            </div>

            {/* Update-specific fields */}
            {mode === 'update' && selectedSource && (
              <>
                <div>
                  <label htmlFor="add_url_patterns" className="block text-sm font-medium mb-1">
                    Additional URL Patterns <span className="text-xs text-muted-foreground">(optional)</span>
                  </label>
                  <input
                    id="add_url_patterns"
                    type="text"
                    value={formData.add_url_patterns}
                    onChange={(e) => setFormData({ ...formData, add_url_patterns: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    placeholder="*new-docs*, *updated-guide*"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Additional URL patterns to include beyond existing ones (comma-separated)
                  </p>
                </div>

                <div>
                  <label htmlFor="exclude_url_patterns" className="block text-sm font-medium mb-1">
                    Exclude URL Patterns <span className="text-xs text-muted-foreground">(optional)</span>
                  </label>
                  <input
                    id="exclude_url_patterns"
                    type="text"
                    value={formData.exclude_url_patterns}
                    onChange={(e) => setFormData({ ...formData, exclude_url_patterns: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    placeholder="*deprecated*, *old-api*"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    URL patterns to exclude from this crawl (comma-separated)
                  </p>
                </div>
              </>
            )}

            {/* Common fields for both modes */}
            <div>
              <label htmlFor="max_depth" className="block text-sm font-medium mb-1">
                Max Depth
              </label>
              <select
                id="max_depth"
                value={formData.max_depth}
                onChange={(e) => {
                  const newDepth = parseInt(e.target.value);
                  setFormData({
                    ...formData,
                    max_depth: newDepth,
                    // Clear URL patterns when switching to single page
                    url_patterns: newDepth === 0 ? '' : formData.url_patterns,
                  });
                }}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              >
                <option value={0}>Single page only</option>
                <option value={1}>1 level deep</option>
                <option value={2}>2 levels deep</option>
                <option value={3}>3 levels deep</option>
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                How many levels of links to follow from the base URL
              </p>
            </div>

            <div>
              <label htmlFor="domain_filter" className="block text-sm font-medium mb-1">
                Domain Restriction
              </label>
              <input
                id="domain_filter"
                type="text"
                value={formData.domain_filter}
                onChange={(e) =>
                  setFormData({ ...formData, domain_filter: e.target.value })
                }
                disabled={mode === 'update'}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
                placeholder="e.g., nextjs.org"
              />
              <p className="text-xs text-muted-foreground mt-1">
                {mode === 'create' 
                  ? "Restrict crawling to this domain. Leave empty to use the domain from base URL."
                  : "Domain restriction from original source (cannot be changed)"
                }
              </p>
            </div>

            {/* URL patterns - only show in create mode or when depth > 0 */}
            {(mode === 'create' || formData.max_depth > 0) && (
              <div className={formData.max_depth === 0 ? 'opacity-50' : ''}>
                <label htmlFor="url_patterns" className="block text-sm font-medium mb-1">
                  URL Patterns <span className="text-xs text-muted-foreground">(optional)</span>
                  {formData.max_depth === 0 && (
                    <span className="text-xs text-muted-foreground ml-2">(disabled for single page)</span>
                  )}
                </label>
                <input
                  id="url_patterns"
                  type="text"
                  value={formData.url_patterns}
                  onChange={(e) =>
                    setFormData({ ...formData, url_patterns: e.target.value })
                  }
                  disabled={formData.max_depth === 0 || mode === 'update'}
                  className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
                  placeholder="*docs*, *guide*, *api*"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {mode === 'create' 
                    ? (formData.max_depth === 0 
                        ? "URL patterns only apply when crawling multiple pages (depth > 0)"
                        : "Filter URLs by patterns (comma-separated). Use * as wildcard. Example: *docs*, *guide*")
                    : "Use 'Additional URL Patterns' field above to add new patterns"
                  }
                </p>
              </div>
            )}

            <div>
              <label htmlFor="max_pages" className="block text-sm font-medium mb-1">
                Max Pages <span className="text-xs text-muted-foreground">(optional)</span>
              </label>
              <input
                id="max_pages"
                type="number"
                value={formData.max_pages || ''}
                onChange={(e) => setFormData({ ...formData, max_pages: e.target.value ? parseInt(e.target.value) : undefined })}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="No limit"
                min="1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum number of pages to crawl. Leave empty for no limit.
              </p>
            </div>

            <div>
              <label htmlFor="max_concurrent_crawls" className="block text-sm font-medium mb-1">
                Max Concurrent Crawls
              </label>
              <input
                id="max_concurrent_crawls"
                type="text"
                inputMode="numeric"
                value={maxConcurrentInput}
                onChange={(e) => {
                  const rawValue = e.target.value;
                  setMaxConcurrentInput(rawValue);
                  
                  // Allow empty string for deletion
                  if (rawValue === '') {
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: 20,
                    });
                    return;
                  }
                  
                  // Parse and validate the number
                  const value = parseInt(rawValue);
                  if (!isNaN(value) && value >= 0 && value <= 100) {
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: value,
                    });
                  } else if (rawValue === '0') {
                    // Explicitly handle 0
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: 0,
                    });
                  }
                }}
                onBlur={() => {
                  // Reset to the actual value if input is invalid
                  const currentValue = formData.max_concurrent_crawls;
                  setMaxConcurrentInput(currentValue.toString());
                }}
                className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono"
                placeholder="5"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum number of concurrent page crawls (1-100). Higher values are faster but use more resources.
              </p>
            </div>
          </div>

          <div className="flex gap-3 p-6 pt-4 border-t border-border">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors disabled:opacity-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || (mode === 'update' && !selectedSource)}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-all disabled:opacity-50 font-medium"
            >
              {isSubmitting 
                ? (mode === 'create' ? 'Creating...' : 'Updating...') 
                : (mode === 'create' ? 'Create Crawl' : 'Update Source')
              }
            </button>
          </div>
        </form>

        {/* Confirmation Dialog for Updates */}
        <ConfirmationDialog
          isOpen={showConfirmDialog}
          title="Update Source"
          message={`Are you sure you want to update "${selectedSource?.name}"? This will start a new crawl job with the specified changes.`}
          confirmText="Update Source"
          cancelText="Cancel"
          onConfirm={handleConfirmSubmit}
          onCancel={handleCancelConfirm}
          variant="default"
          isConfirming={isSubmitting}
        />
      </div>
    </div>
  );
};