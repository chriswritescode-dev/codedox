import React from 'react';

type DialogMode = 'create' | 'update';

interface CrawlConfigFieldsProps {
  mode: DialogMode;
  formData: {
    max_depth: number;
    domain_filter: string;
    url_patterns: string;
    max_pages: number | undefined;
  };
  maxConcurrentInput: string;
  onChange: (field: string, value: string | number | undefined) => void;
  onMaxConcurrentChange: (value: string) => void;
  onMaxConcurrentBlur: () => void;
}

export const CrawlConfigFields: React.FC<CrawlConfigFieldsProps> = ({
  mode,
  formData,
  maxConcurrentInput,
  onChange,
  onMaxConcurrentChange,
  onMaxConcurrentBlur,
}) => {
  return (
    <>
      <div>
        <label htmlFor="max_depth" className="block text-sm font-medium mb-1">
          Max Depth
        </label>
        <select
          id="max_depth"
          value={formData.max_depth}
          onChange={(e) => {
            const newDepth = parseInt(e.target.value);
            onChange('max_depth', newDepth);
            onChange('url_patterns', newDepth === 0 ? '' : formData.url_patterns);
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
          onChange={(e) => onChange('domain_filter', e.target.value)}
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
            onChange={(e) => onChange('url_patterns', e.target.value)}
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
          onChange={(e) => onChange('max_pages', e.target.value ? parseInt(e.target.value) : undefined)}
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
          onChange={(e) => onMaxConcurrentChange(e.target.value)}
          onBlur={onMaxConcurrentBlur}
          className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono"
          placeholder="5"
        />
        <p className="text-xs text-muted-foreground mt-1">
          Maximum number of concurrent page crawls (1-100). Higher values are faster but use more resources.
        </p>
      </div>
    </>
  );
};