import React, { useState, useEffect, useRef, useMemo } from 'react';
import { ChevronDown, X, Search } from 'lucide-react';
import { SourceOption } from '../lib/api';
import { useDebounce } from '../hooks/useDebounce';

interface SourceAutocompleteProps {
  sources: SourceOption[];
  selectedSource: SourceOption | null;
  onSourceSelect: (source: SourceOption | null) => void;
  placeholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
}

export const SourceAutocomplete: React.FC<SourceAutocompleteProps> = ({
  sources,
  selectedSource,
  onSourceSelect,
  placeholder = "Search for a source...",
  disabled = false,
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const debouncedQuery = useDebounce(searchQuery, 200);

  const filteredSources = useMemo(() => {
    if (!debouncedQuery.trim()) {
      return sources.slice(0, 50);
    }
    
    const query = debouncedQuery.toLowerCase();
    return sources
      .filter(source => 
        source.name.toLowerCase().includes(query) ||
        (source.version && source.version.toLowerCase().includes(query)) ||
        source.display_name.toLowerCase().includes(query)
      )
      .slice(0, 50);
  }, [debouncedQuery, sources]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setHighlightedIndex(0);
  }, [filteredSources]);

  useEffect(() => {
    if (isOpen && listRef.current && highlightedIndex >= 0) {
      const highlightedElement = listRef.current.children[highlightedIndex] as HTMLElement;
      highlightedElement?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [highlightedIndex, isOpen]);

  const handleInputChange = (value: string) => {
    setSearchQuery(value);
    setIsOpen(true);
    
    if (!value.trim()) {
      onSourceSelect(null);
    }
  };

  const handleSourceSelect = (source: SourceOption) => {
    onSourceSelect(source);
    setSearchQuery('');
    setIsOpen(false);
  };

  const handleClear = () => {
    setSearchQuery('');
    onSourceSelect(null);
    setIsOpen(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      inputRef.current?.blur();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredSources.length > 0 && isOpen && highlightedIndex >= 0) {
        handleSourceSelect(filteredSources[highlightedIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex(prev => 
        prev < filteredSources.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => prev > 0 ? prev - 1 : 0);
    } else if (e.key === 'Tab') {
      setIsOpen(false);
    }
  };

  const displayValue = selectedSource 
    ? selectedSource.display_name 
    : searchQuery;

  const showClearButton = (selectedSource || searchQuery) && !disabled && !isLoading;

  return (
    <div ref={dropdownRef} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={displayValue}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          disabled={disabled || isLoading}
          placeholder={placeholder}
          className="w-full pl-10 pr-20 py-2 border border-input rounded-lg bg-background focus:outline-hidden focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:cursor-not-allowed disabled:bg-secondary/50"
        />
        
        {showClearButton && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-10 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            tabIndex={-1}
          >
            <X className="h-4 w-4" />
          </button>
        )}
        
        <button
          type="button"
          onClick={() => !disabled && !isLoading && setIsOpen(!isOpen)}
          disabled={disabled || isLoading}
          className="absolute right-2 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors disabled:cursor-not-allowed"
          tabIndex={-1}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isOpen && !disabled && (
        <div className="absolute z-50 w-full mt-2 bg-background border border-input rounded-lg shadow-lg max-h-80 overflow-hidden">
          {isLoading ? (
            <div className="px-4 py-3 text-center text-sm text-muted-foreground">
              Loading sources...
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="px-4 py-3 text-center text-sm text-muted-foreground">
              {searchQuery ? 'No matching sources found' : 'No sources available'}
            </div>
          ) : (
            <ul ref={listRef} className="overflow-y-auto max-h-80">
              {filteredSources.map((source, index) => (
                <li key={source.id}>
                  <button
                    type="button"
                    onClick={() => handleSourceSelect(source)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={`w-full px-4 py-3 text-left hover:bg-secondary border-b border-border last:border-b-0 transition-colors ${
                      index === highlightedIndex ? 'bg-secondary' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex flex-col min-w-0 flex-1 mr-4">
                        <span className="font-medium text-sm truncate">{source.name}</span>
                        {source.version && (
                          <span className="text-xs text-muted-foreground">v{source.version}</span>
                        )}
                      </div>
                      <div className="flex flex-col items-end text-xs text-muted-foreground shrink-0">
                        <span>{source.documents_count} docs</span>
                        <span>{source.snippets_count} snippets</span>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};