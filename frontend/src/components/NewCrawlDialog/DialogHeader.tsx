import React from 'react';
import { X } from 'lucide-react';

interface DialogHeaderProps {
  title: string;
  onClose: () => void;
}

export const DialogHeader: React.FC<DialogHeaderProps> = ({ title, onClose }) => {
  return (
    <div className="flex items-center justify-between p-6 pb-4 border-b border-border">
      <h2 className="text-xl font-semibold">{title}</h2>
      <button
        onClick={onClose}
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        <X className="h-5 w-5" />
      </button>
    </div>
  );
};