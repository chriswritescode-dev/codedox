import React, { useState, useEffect, useMemo } from 'react';

import { useToast } from '../hooks/useToast';
import { useKeyboardShortcut } from '../hooks/useKeyboardShortcut';
import { ConfirmationDialog } from './ConfirmationDialog';
import { SourceOption } from '../lib/api';
import { useSources } from '../hooks/useSources';
import {
  DialogHeader,
  SourceSelector,
  BasicFields,
  UpdateFields,
  CrawlConfigFields,
  DialogActions,
} from './NewCrawlDialog/index';

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
    if (selectedSource && mode === 'update') {
      setFormData(prev => ({
        ...prev,
        name: selectedSource.name,
        version: selectedSource.version || '',
        base_url: selectedSource.base_url,
      }));
    }
  }, [selectedSource, mode]);

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
      <div className="bg-card border-2 border-border rounded-lg w-full max-w-2xl h-[85vh] shadow-2xl animate-slide-up flex flex-col">
        <DialogHeader
          title={mode === 'create' ? 'Create New Crawl' : 'Update Existing Source'}
          mode={mode}
          onModeChange={handleModeChange}
          onClose={handleClose}
        />

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            
            {/* Source Selection for Update Mode */}
            {mode === 'update' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Select Source to Update
                </label>
                <SourceSelector
                  sources={sources}
                  selectedSource={selectedSource}
                  onSourceSelect={setSelectedSource}
                  isSubmitting={isSubmitting}
                  isLoading={isLoadingSources}
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Basic Information
              </label>
              <BasicFields
                mode={mode}
                formData={{
                  name: formData.name,
                  version: formData.version,
                  base_url: formData.base_url,
                }}
                onChange={(field, value) => setFormData({ ...formData, [field]: value })}
                onBaseUrlChange={(value) => {
                  setFormData((prev) => {
                    let domain = prev.domain_filter;
                    if (mode === 'create' && !prev.domain_filter && value) {
                      try {
                        const parsed = new URL(value);
                        domain = parsed.hostname;
                      } catch (err) {
                        // Invalid URL, keep existing domain
                      }
                    }
                    return { ...prev, base_url: value, domain_filter: domain };
                  });
                }}
                selectedSource={selectedSource}
              />
            </div>

            {/* Update-specific fields */}
            {mode === 'update' && selectedSource && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  URL Pattern Updates
                </label>
                <UpdateFields
                  addUrlPatterns={formData.add_url_patterns}
                  excludeUrlPatterns={formData.exclude_url_patterns}
onChange={(field, value) => setFormData(prev => ({ ...prev, [field]: value }))}
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Crawl Configuration
              </label>
              <CrawlConfigFields
                mode={mode}
                formData={{
                  max_depth: formData.max_depth,
                  domain_filter: formData.domain_filter,
                  url_patterns: formData.url_patterns,
                  max_pages: formData.max_pages,
                }}
                maxConcurrentInput={maxConcurrentInput}
                onChange={(field, value) => setFormData({ ...formData, [field]: value })}
                onMaxConcurrentChange={(value) => {
                  setMaxConcurrentInput(value);
                  
                  if (value === '') {
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: 20,
                    });
                    return;
                  }
                  
                  const parsedValue = parseInt(value);
                  if (!isNaN(parsedValue) && parsedValue >= 0 && parsedValue <= 100) {
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: parsedValue,
                    });
                  } else if (value === '0') {
                    setFormData({
                      ...formData,
                      max_concurrent_crawls: 0,
                    });
                  }
                }}
                onMaxConcurrentBlur={() => {
                  const currentValue = formData.max_concurrent_crawls;
                  setMaxConcurrentInput(currentValue.toString());
                }}
              />
            </div>
          </div>

          <DialogActions
              mode={mode}
              isSubmitting={isSubmitting}
              isUpdateDisabled={mode === 'update' && !selectedSource}
              onCancel={handleClose}
            />
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