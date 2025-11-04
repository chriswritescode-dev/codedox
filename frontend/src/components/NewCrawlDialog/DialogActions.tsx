import React from 'react';

type DialogMode = 'create' | 'update';

interface DialogActionsProps {
  mode: DialogMode;
  isSubmitting: boolean;
  isUpdateDisabled: boolean;
  onCancel: () => void;
}

export const DialogActions: React.FC<DialogActionsProps> = ({
  mode,
  isSubmitting,
  isUpdateDisabled,
  onCancel,
}) => {
  return (
    <div className="flex gap-3 p-6 pt-4 border-t border-border">
      <button
        type="button"
        onClick={onCancel}
        disabled={isSubmitting}
        className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors disabled:opacity-50 font-medium"
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={isSubmitting || isUpdateDisabled}
        className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-all disabled:opacity-50 font-medium"
      >
        {isSubmitting 
          ? (mode === 'create' ? 'Creating...' : 'Updating...') 
          : (mode === 'create' ? 'Create Crawl' : 'Update Source')
        }
      </button>
    </div>
  );
};