import React from 'react';
import { Plus, RefreshCw } from 'lucide-react';

type DialogMode = 'create' | 'update';

interface ModeSelectorProps {
  mode: DialogMode;
  onModeChange: (mode: DialogMode) => void;
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({ mode, onModeChange }) => {
  return (
    <div className="px-6 py-4 border-b border-border">
      <div className="flex gap-4">
        <button
          type="button"
          onClick={() => onModeChange('create')}
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
          onClick={() => onModeChange('update')}
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
  );
};