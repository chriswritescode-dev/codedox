import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useToast } from '../hooks/useToast';

interface NewCrawlDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    name?: string;
    base_url: string;
    max_depth: number;
    domain_filter?: string;
    url_patterns?: string[];
    max_concurrent_crawls?: number;
  }) => void;
  isSubmitting?: boolean;
}

export const NewCrawlDialog: React.FC<NewCrawlDialogProps> = ({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}) => {
  const toast = useToast();
  const [formData, setFormData] = useState({
    name: '',
    base_url: '',
    max_depth: 1,
    domain_filter: '',
    url_patterns: '',
    max_concurrent_crawls: 5,
  });
  
  const [maxConcurrentInput, setMaxConcurrentInput] = useState('5');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.base_url) {
      toast.warning('Please enter a base URL');
      return;
    }
    // Use the current max_concurrent_crawls value, falling back to form data
    const finalMaxConcurrent = maxConcurrentInput ? parseInt(maxConcurrentInput) || formData.max_concurrent_crawls : formData.max_concurrent_crawls;
    
    const submitData = {
      ...formData,
      name: formData.name || undefined, // Allow empty name for auto-detection
      domain_filter: formData.domain_filter || undefined,
      url_patterns: formData.max_depth > 0 && formData.url_patterns 
        ? formData.url_patterns.split(',').map(p => p.trim()).filter(p => p)
        : undefined,
      max_concurrent_crawls: Math.max(0, Math.min(100, finalMaxConcurrent)), // Clamp between 0-100
    };
    onSubmit(submitData);
  };

  const handleClose = () => {
    setFormData({ name: '', base_url: '', max_depth: 1, domain_filter: '', url_patterns: '', max_concurrent_crawls: 5 });
    setMaxConcurrentInput('5');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-slate-600/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-card border-2 border-border rounded-lg p-6 w-full max-w-md shadow-2xl animate-slide-up">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Create New Crawl</h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-1">
              Name <span className="text-xs text-muted-foreground">(optional - auto-detected if empty)</span>
            </label>
            <input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              placeholder="Will be auto-detected from site (e.g., Next.js Documentation)"
            />
          </div>

          <div>
            <label htmlFor="base_url" className="block text-sm font-medium mb-1">
              Base URL <span className="text-destructive">*</span>
            </label>
            <input
              id="base_url"
              type="url"
              value={formData.base_url}
              onChange={(e) => {
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
              }}
              className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              placeholder="https://nextjs.org/docs"
              required
            />
          </div>

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
              className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              placeholder="e.g., nextjs.org"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Restrict crawling to this domain. Leave empty to use the domain from base URL.
            </p>
          </div>

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
              disabled={formData.max_depth === 0}
              className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
              placeholder="*docs*, *guide*, *api*"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {formData.max_depth === 0 
                ? "URL patterns only apply when crawling multiple pages (depth > 0)"
                : "Filter URLs by patterns (comma-separated). Use * as wildcard. Example: *docs*, *guide*"}
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

          <div className="flex gap-3 pt-4">
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
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-all disabled:opacity-50 font-medium"
            >
              {isSubmitting ? 'Creating...' : 'Create Crawl'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};