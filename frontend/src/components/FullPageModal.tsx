import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  X,
  ExternalLink,
  Copy,
  Check,
  AlertCircle,
  FileText,
  Search,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { api } from "../lib/api";
import { Link } from "react-router-dom";
import { useKeyboardShortcut } from "../hooks/useKeyboardShortcut";

interface FullPageModalProps {
  url: string;
  isOpen: boolean;
  onClose: () => void;
  onNavigateToSnippets?: () => void;
}

export const FullPageModal: React.FC<FullPageModalProps> = ({
  url,
  isOpen,
  onClose,
  onNavigateToSnippets,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [copied, setCopied] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentMatch, setCurrentMatch] = useState(0);
  const [totalMatches, setTotalMatches] = useState(0);
  const [highlightedContent, setHighlightedContent] = useState<string>("");
  const contentRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && url) {
      fetchPageMarkdown();
    }
  }, [isOpen, url]);

  // Handle keyboard shortcuts
  useKeyboardShortcut('Escape', onClose, isOpen);
  
  useKeyboardShortcut('f', () => {
    if (isOpen) {
      searchInputRef.current?.focus();
    }
  }, isOpen);

  const fetchPageMarkdown = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getPageMarkdown(url);
      if (response.status === "success") {
        setData(response);
      } else if (response.status === "no_content") {
        setError(response.message || "No markdown content available");
        setData(response);
      } else {
        setError("Failed to fetch page content");
      }
    } catch (err) {
      setError("Failed to fetch page content");
      console.error("Error fetching page markdown:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyContent = async () => {
    if (data?.markdown_content) {
      await navigator.clipboard.writeText(data.markdown_content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleOpenInNewTab = () => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  // Highlight search matches in content
  const highlightMatches = useCallback((text: string, query: string) => {
    if (!query) return text;

    const regex = new RegExp(
      `(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
      "gi",
    );
    const matches = text.match(regex);
    setTotalMatches(matches ? matches.length : 0);
    setCurrentMatch(matches && matches.length > 0 ? 1 : 0);

    return text;
  }, []);

  // Navigate between search matches
  const navigateSearch = useCallback(
    (direction: "next" | "prev") => {
      if (totalMatches === 0) return;

      let newMatch = currentMatch;
      if (direction === "next") {
        newMatch = currentMatch >= totalMatches ? 1 : currentMatch + 1;
      } else {
        newMatch = currentMatch <= 1 ? totalMatches : currentMatch - 1;
      }
      setCurrentMatch(newMatch);

      // Scroll to the match using element ID
      setTimeout(() => {
        const targetElement = document.getElementById(
          `search-match-${newMatch}`,
        );
        if (targetElement) {
          targetElement.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
        }
      }, 50); // Small delay to ensure DOM is updated
    },
    [currentMatch, totalMatches],
  );

  // Handle search input change
  useEffect(() => {
    if (data?.markdown_content && searchQuery) {
      const highlighted = highlightMatches(data.markdown_content, searchQuery);
      setHighlightedContent(highlighted);

      // Auto-scroll to first match when new search
      if (totalMatches > 0) {
        setTimeout(() => {
          const firstMatch = document.getElementById("search-match-1");
          if (firstMatch) {
            firstMatch.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
          }
        }, 100);
      }
    } else {
      setHighlightedContent("");
      setTotalMatches(0);
      setCurrentMatch(0);
    }
  }, [searchQuery, data, highlightMatches]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="bg-background rounded-lg shadow-xl w-[90%] max-w-[1600px] max-h-[90vh] flex flex-col mx-auto">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="min-w-0">
              <h2 className="text-lg font-semibold truncate">
                {data?.document?.title || "Loading..."}
              </h2>
              {data?.source && (
                <p className="text-sm text-muted-foreground">
                  {data.source.name}
                </p>
              )}
            </div>
          </div>

          {/* Search box in center */}
          {data?.markdown_content && (
            <div className="flex items-center gap-2 mx-4 border border-border rounded-lg px-3 py-1.5 bg-secondary/30">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && totalMatches > 0) {
                    e.preventDefault();
                    navigateSearch("next");
                  } else if (
                    e.key === "Enter" &&
                    e.shiftKey &&
                    totalMatches > 0
                  ) {
                    e.preventDefault();
                    navigateSearch("prev");
                  }
                }}
                placeholder="Search content..."
                className="bg-transparent outline-none text-sm w-48"
              />
              {totalMatches > 0 && (
                <>
                  <span className="text-xs text-muted-foreground ml-2">
                    {currentMatch}/{totalMatches}
                  </span>
                  <div className="flex items-center gap-0.5 ml-1">
                    <button
                      onClick={() => navigateSearch("prev")}
                      className="p-0.5 hover:bg-secondary rounded"
                      title="Previous (Shift+Enter)"
                    >
                      <ChevronUp className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => navigateSearch("next")}
                      className="p-0.5 hover:bg-secondary rounded"
                      title="Next (Enter)"
                    >
                      <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </>
              )}
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="p-0.5 hover:bg-secondary rounded ml-1"
                  title="Clear search"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            {data?.source?.id && data?.document?.id && (
              <Link
                to={`/sources/${data.source.id}/documents/${data.document.id}`}
                onClick={onNavigateToSnippets || onClose}
                className="text-primary hover:underline text-sm font-medium mr-2"
              >
                View Snippets
              </Link>
            )}
            <button
              onClick={handleCopyContent}
              disabled={!data?.markdown_content}
              className="p-2 hover:bg-secondary rounded-lg transition-colors disabled:opacity-50"
              title="Copy content"
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>
            <button
              onClick={handleOpenInNewTab}
              className="p-2 hover:bg-secondary rounded-lg transition-colors"
              title="Open in new tab"
            >
              <ExternalLink className="h-4 w-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-secondary rounded-lg transition-colors"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 relative">
          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          )}

          {error && (
            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                <div>
                  <p className="text-destructive-foreground">{error}</p>
                  {data?.note && (
                    <p className="text-sm text-destructive/80 mt-1">
                      {data.note}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {!loading && data?.markdown_content && (
            <div className="prose dark:prose-invert max-w-none w-full">
              <div
                ref={contentRef}
                className="font-mono text-sm bg-secondary p-4 rounded-lg overflow-x-hidden"
                style={{ 
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  overflowWrap: 'break-word'
                }}
              >
                {searchQuery && highlightedContent ? (
                  <HighlightedText
                    text={data.markdown_content}
                    query={searchQuery}
                    currentMatch={currentMatch}
                  />
                ) : (
                  data.markdown_content
                )}
              </div>
            </div>
          )}

          {!loading && data?.document && !data?.markdown_content && (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
              <p className="text-muted-foreground">
                No markdown content available for this document
              </p>
              <p className="text-sm text-muted-foreground/70 mt-2">
                This document was crawled before markdown storage was enabled
              </p>
            </div>
          )}
        </div>

        {/* Footer with metadata */}
        {data?.document && (
          <div className="px-6 py-3 border-t border-border bg-secondary/50">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <div className="flex items-center gap-4">
                <span>
                  URL:{" "}
                  <code className="text-xs bg-secondary px-1 py-0.5 rounded">
                    {url}
                  </code>
                </span>
                {data.document.content_length && (
                  <span>
                    {data.document.content_length.toLocaleString()} characters
                  </span>
                )}
              </div>
              {data.document.last_crawled && (
                <span>
                  Last crawled:{" "}
                  {new Date(data.document.last_crawled).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Component to render highlighted text
const HighlightedText: React.FC<{
  text: string;
  query: string;
  currentMatch: number;
}> = ({ text, query, currentMatch }) => {
  if (!query) return <>{text}</>;
  
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  const parts = text.split(regex);
  let matchIndex = 0;
  
  return (
    <>
      {parts.map((part, index) => {
        if (index % 2 === 1) {
          // This is a match
          matchIndex++;
          const isCurrentMatch = matchIndex === currentMatch;
          return (
            <mark
              key={index}
              id={`search-match-${matchIndex}`}
              className={
                isCurrentMatch
                  ? "bg-yellow-400 dark:bg-yellow-500 text-black px-0.5 rounded scroll-mt-20"
                  : "bg-yellow-200 dark:bg-yellow-700 text-black dark:text-white px-0.5 rounded"
              }
            >
              {part}
            </mark>
          );
        }
        return <React.Fragment key={index}>{part}</React.Fragment>;
      })}
    </>
  );
};

