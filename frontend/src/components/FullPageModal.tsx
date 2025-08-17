import React, { useEffect, useState } from "react";
import {
  X,
  ExternalLink,
  Copy,
  Check,
  AlertCircle,
  FileText,
} from "lucide-react";
import { api } from "../lib/api";
import { Link } from "react-router-dom";

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

  useEffect(() => {
    if (isOpen && url) {
      fetchPageMarkdown();
    }
  }, [isOpen, url]);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

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

  if (!isOpen) return null;
console.log(url);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="bg-background rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] flex flex-col mx-4">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="min-w-0 ">
              <h2 className="text-lg font-semibold truncate">
                {data?.document?.title || "Loading..."}
              </h2>
              {data?.source && (
                <p className="text-sm text-muted-foreground">
                  {data.source.name}
                </p>
              )}
            </div>
            {data?.source?.id && data?.document?.id && (
              <Link
                to={`/sources/${data.source.id}/documents/${data.document.id}`}
                onClick={onNavigateToSnippets || onClose}
                className="ml-auto text-primary hover:underline text-sm font-medium"
              >
                View Document Snippets
              </Link>
            )}
          </div>
          <div className="flex items-center gap-2">
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
        <div className="flex-1 overflow-auto p-6">
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
            <div className="prose dark:prose-invert max-w-none">
              <pre className="whitespace-pre-wrap font-mono text-sm bg-secondary p-4 rounded-lg overflow-x-auto">
                {data.markdown_content}
              </pre>
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

