import { forwardRef, useEffect, useRef, useState, useCallback } from "react";
import { Search, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

interface SearchBarProps {
  onChange: (value: string) => void;
  placeholder?: string;
  onFocus?: () => void;
  onBlur?: () => void;
  debounceMs?: number;
}

export const SearchBar = forwardRef<HTMLInputElement, SearchBarProps>(
  ({ onChange, placeholder = "Search sources by name or URL", debounceMs = 300 }) => {
    const [searchParams] = useSearchParams();
    const urlValue = searchParams.get("q") || "";
    const [localValue, setLocalValue] = useState(urlValue);

    const searchInputRef = useRef<HTMLInputElement>(null);
    const debounceTimerRef = useRef<NodeJS.Timeout>();

    const isFocused = !!urlValue;

    useEffect(() => {
      if (isFocused && searchInputRef.current) {
        searchInputRef.current.value = urlValue;
        searchInputRef.current.focus();
      }
    }, []);

    useEffect(() => {
      setLocalValue(urlValue);
    }, [urlValue]);

    const debouncedOnChange = useCallback((value: string) => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      
      debounceTimerRef.current = setTimeout(() => {
        onChange(value);
      }, debounceMs);
    }, [onChange, debounceMs]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setLocalValue(value);
      debouncedOnChange(value);
    }, [debouncedOnChange]);

    const handleClear = useCallback(() => {
      setLocalValue("");
      onChange("");
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    }, [onChange]);

    useEffect(() => {
      return () => {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
      };
    }, []);

    return (
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          ref={searchInputRef}
          type="text"
          placeholder={placeholder}
          value={localValue}
          onChange={handleInputChange}
          className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
        />
        {localValue && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  },
);

SearchBar.displayName = "SearchBar";

