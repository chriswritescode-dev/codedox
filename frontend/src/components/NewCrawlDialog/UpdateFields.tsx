import React from 'react';

interface UpdateFieldsProps {
  addUrlPatterns: string;
  excludeUrlPatterns: string;
  onChange: (field: string, value: string) => void;
}

export const UpdateFields: React.FC<UpdateFieldsProps> = ({
  addUrlPatterns,
  excludeUrlPatterns,
  onChange,
}) => {
  return (
    <>
      <div>
        <label htmlFor="add_url_patterns" className="block text-sm font-medium mb-1">
          Additional URL Patterns <span className="text-xs text-muted-foreground">(optional)</span>
        </label>
        <input
          id="add_url_patterns"
          type="text"
          value={addUrlPatterns}
          onChange={(e) => onChange('add_url_patterns', e.target.value)}
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
          value={excludeUrlPatterns}
          onChange={(e) => onChange('exclude_url_patterns', e.target.value)}
          className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
          placeholder="*deprecated*, *old-api*"
        />
        <p className="text-xs text-muted-foreground mt-1">
          URL patterns to exclude from this crawl (comma-separated)
        </p>
      </div>
    </>
  );
};