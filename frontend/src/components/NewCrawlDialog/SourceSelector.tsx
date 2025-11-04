import React from 'react';
import { SourceAutocomplete } from '../SourceAutocomplete';
import { SourceOption } from '../../lib/api';

interface SourceSelectorProps {
  sources: SourceOption[];
  selectedSource: SourceOption | null;
  onSourceSelect: (source: SourceOption | null) => void;
  isSubmitting: boolean;
  isLoading: boolean;
}

export const SourceSelector: React.FC<SourceSelectorProps> = ({
  sources,
  selectedSource,
  onSourceSelect,
  isSubmitting,
  isLoading,
}) => {
  return (
    <div>
      <label htmlFor="source_select" className="block text-sm font-medium mb-1">
        Select Source <span className="text-destructive">*</span>
      </label>
      <SourceAutocomplete
        sources={sources}
        selectedSource={selectedSource}
        onSourceSelect={onSourceSelect}
        placeholder="Search for a source to update..."
        disabled={isSubmitting}
        isLoading={isLoading}
      />
      {selectedSource && (
        <div className="mt-2 p-2 bg-secondary/50 rounded-md">
          <div className="text-xs text-muted-foreground">
            <span className="font-medium">Current Stats:</span> {selectedSource.documents_count} documents, {selectedSource.snippets_count} snippets
          </div>
        </div>
      )}
    </div>
  );
};