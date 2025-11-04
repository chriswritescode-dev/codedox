import React from 'react';
import { X, Plus, RefreshCw } from 'lucide-react';

type DialogMode = 'create' | 'update';

interface DialogHeaderProps {
  title: string;
  mode: DialogMode;
  onModeChange: (mode: DialogMode) => void;
  onClose: () => void;
}

export const DialogHeader: React.FC<DialogHeaderProps> = ({ title, mode, onModeChange, onClose }) => {
  return (
    <div>
      <div className="flex items-center justify-between p-6 pb-0">
        <h2 className="text-xl font-semibold">{title}</h2>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="px-6">
        <div className="flex gap-1 border-b border-border">
          <button
            type="button"
            onClick={() => onModeChange('create')}
            className={`flex items-center gap-2 px-4 py-3 rounded-t-lg font-medium transition-all border-b-2 -mb-px ${
              mode === 'create'
                ? 'bg-primary/10 text-primary border-primary'
                : 'text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <Plus className="h-4 w-4" />
            New Source
          </button>
          <button
            type="button"
            onClick={() => onModeChange('update')}
            className={`flex items-center gap-2 px-4 py-3 rounded-t-lg font-medium transition-all border-b-2 -mb-px ${
              mode === 'update'
                ? 'bg-primary/10 text-primary border-primary'
                : 'text-muted-foreground border-transparent hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <RefreshCw className="h-4 w-4" />
            Update Existing
          </button>
        </div>
      </div>
    </div>
  );
};