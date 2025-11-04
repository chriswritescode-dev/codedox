import React from 'react';

type DialogMode = 'create' | 'update';

interface BasicFieldsProps {
  mode: DialogMode;
  formData: {
    name: string;
    version: string;
    base_url: string;
  };
  onChange: (field: string, value: string) => void;
  onBaseUrlChange: (value: string) => void;
  selectedSource?: any;
}

export const BasicFields: React.FC<BasicFieldsProps> = ({
  mode,
  formData,
  onChange,
  onBaseUrlChange,
  selectedSource,
}) => {
  return (
    <>
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
          onChange={(e) => onChange('name', e.target.value)}
          disabled={mode === 'update' && !!selectedSource}
          className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
          placeholder={mode === 'create' ? "Will be auto-detected from site (e.g., Next.js Documentation)" : "Source name"}
        />
      </div>

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
          onChange={(e) => onChange('version', e.target.value)}
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

      <div>
        <label htmlFor="base_url" className="block text-sm font-medium mb-1">
          Base URL <span className="text-destructive">*</span>
          {mode === 'update' && <span className="text-xs text-muted-foreground ml-2">(can be updated for new crawl)</span>}
        </label>
        <input
          id="base_url"
          type="url"
          value={formData.base_url}
          onChange={(e) => onBaseUrlChange(e.target.value)}
          className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
          placeholder="https://nextjs.org/docs"
          required
        />
      </div>
    </>
  );
};