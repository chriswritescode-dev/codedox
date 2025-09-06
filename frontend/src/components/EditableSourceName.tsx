import React, { useState, useRef, useEffect } from 'react';
import { Edit3, Check, X, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

interface EditableSourceNameProps {
  id: string;
  name: string;
	version?: string;
  onUpdate: (id: string, newName: string, newVersion?: string) => Promise<void>;
  className?: string;
}

export const EditableSourceName: React.FC<EditableSourceNameProps> = ({
  id,
  name,
  onUpdate,
	version,
  className = '',
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState({name: name, version: version || ''});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setEditValue({name: name, version: version || ''});
  }, [name, version]);

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
    setEditValue({name: name, version: version || ''});
    setIsEditing(false);
    setError(null);
  };

  const handleSave = async () => {
    const trimmedName = editValue.name.trim();
    const trimmedVersion = editValue.version.trim();
    
    if (!trimmedName) {
      setError('Name cannot be empty');
      return;
    }

    // Check if nothing changed
    if (trimmedName === name && trimmedVersion === (version || '')) {
      setIsEditing(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await onUpdate(id, trimmedName, trimmedVersion || undefined);
      setIsEditing(false);
    } catch (err) {
      // Extract error message from API response
      let errorMsg = 'Failed to update';
      if (err instanceof Error) {
        // Try to parse as JSON for API error response
        try {
          const match = err.message.match(/\{.*\}/);
          if (match) {
            const parsed = JSON.parse(match[0]);
            errorMsg = parsed.detail || parsed.message || err.message;
          } else {
            errorMsg = err.message;
          }
        } catch {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
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

  const handleInputChange = (field: 'name' | 'version', value: string) => {
    setEditValue(prev => ({...prev, [field]: value}));
    setError(null);
  };

  if (isEditing) {
    return (
      <div className={`relative inline-flex items-start gap-3 p-3 bg-background border border-border rounded-lg shadow-sm ${className}`}>
        <div className="flex items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <input
              ref={inputRef}
              type="text"
              value={editValue.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              onKeyDown={handleKeyDown}
              className="px-3 py-1.5 text-sm border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent min-w-[200px] bg-background"
              disabled={isLoading}
              placeholder="Source name"
            />
          </div>
          
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Version</label>
            <input
              type="text"
              value={editValue.version}
              onChange={(e) => handleInputChange('version', e.target.value)}
              onKeyDown={handleKeyDown}
              className="px-3 py-1.5 text-sm border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent w-24 bg-background"
              disabled={isLoading}
              placeholder="1.0.0"
            />
          </div>
        </div>
        
        <div className="flex items-center gap-1 self-end">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          ) : (
            <>
              <button
                onClick={handleSave}
                className="p-1.5 text-green-600 hover:text-green-700 hover:bg-green-100 rounded-md transition-colors"
                title="Save changes"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={handleCancel}
                className="p-1.5 text-red-600 hover:text-red-700 hover:bg-red-100 rounded-md transition-colors"
                title="Cancel"
                data-cancel-button="true"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
        
        {error && (
          <div className="absolute -bottom-6 left-3 text-xs text-red-500">
            {error}
          </div>
        )}
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
           {version && (
             <span className="text-sm text-muted-foreground ml-1">
               v{version}
             </span>
           )}
         </Link>

      <button
        onClick={handleEdit}
        className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-foreground rounded transition-opacity"
        title="Edit name and version"
      >
        <Edit3 className="h-4 w-4" />
      </button>
    </div>
  );
};
