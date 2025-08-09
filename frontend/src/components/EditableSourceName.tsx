import React, { useState, useRef, useEffect } from 'react';
import { Edit3, Check, X, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

interface EditableSourceNameProps {
  id: string;
  name: string;
  onUpdate: (id: string, newName: string) => Promise<void>;
  className?: string;
}

export const EditableSourceName: React.FC<EditableSourceNameProps> = ({
  id,
  name,
  onUpdate,
  className = '',
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(name);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setEditValue(name);
  }, [name]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleEdit = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsEditing(true);
    setError(null);
  };

  const handleCancel = () => {
    setEditValue(name);
    setIsEditing(false);
    setError(null);
  };

  const handleSave = async () => {
    const trimmedValue = editValue.trim();
    
    if (!trimmedValue) {
      setError('Name cannot be empty');
      return;
    }

    if (trimmedValue === name) {
      setIsEditing(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onUpdate(id, trimmedValue);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update name');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div className={`inline-flex items-center gap-2 ${className}`}>
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={(e) => {
              // Don't save on blur if clicking cancel button
              const relatedTarget = e.relatedTarget as HTMLElement;
              if (relatedTarget && relatedTarget.getAttribute('data-cancel-button')) {
                return;
              }
              handleSave();
            }}
            className="px-2 py-1 text-sm border border-input rounded focus:outline-none focus:ring-2 focus:ring-primary min-w-32"
            disabled={isLoading}
          />
          {error && (
            <div className="absolute top-full left-0 mt-1 text-xs text-red-500 whitespace-nowrap">
              {error}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-1">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : (
            <>
              <button
                onClick={handleSave}
                className="p-1 text-green-600 hover:text-green-700 rounded"
                title="Save"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={handleCancel}
                className="p-1 text-red-600 hover:text-red-700 rounded"
                title="Cancel"
                data-cancel-button="true"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div> 
    );
  }



  return (
    <div className={`inline-flex items-center gap-2 group ${className}`}>
			  <Link 
          to={`/sources/${id}`} 
          className="text-md text-primary hover:text-primary/80 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
           {name}
        </Link>

      <button
        onClick={handleEdit}
        className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-foreground rounded transition-opacity"
        title="Edit name"
      >
        <Edit3 className="h-4 w-4" />
      </button>
    </div>
  );
};
