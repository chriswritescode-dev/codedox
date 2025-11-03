import { useState, useEffect } from "react";
import { X, RefreshCw, Sparkles, AlertTriangle, Trash2, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { useKeyboardShortcut } from "../hooks/useKeyboardShortcut";
import { useWebSocketSubscription } from "../hooks/useWebSocketSubscription";
import { WebSocketMessageType } from "../lib/websocketTypes";

export type ActionType = 'recrawl' | 'regenerate' | 'delete' | 'retry' | 'custom';

interface ActionDialogProps {
  isOpen: boolean;
  type: ActionType;
  title?: string;
  message?: string;
  sourceName?: string;
  sourceUrl?: string;
  sourceId?: string;
  itemCount?: number;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'destructive';
  onConfirm: (options?: { ignoreHash?: boolean }) => void;
  onCancel: () => void;
  isConfirming?: boolean;
  showForceRegenerateOption?: boolean;
  customIcon?: React.ReactNode;
  enableProgressTracking?: boolean;
}

export function ActionDialog({
  isOpen,
  type,
  title,
  message,
  sourceName,
  sourceUrl,
  sourceId,
  itemCount,
  confirmText,

  variant = 'default',
  onConfirm,
  onCancel,
  isConfirming = false,
  showForceRegenerateOption = false,
  customIcon,
  enableProgressTracking = false,
}: ActionDialogProps) {
  const [ignoreHash, setIgnoreHash] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'error'>('idle');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const { lastMessage, isConnected, reset: resetWebSocket } = useWebSocketSubscription({
    sourceId,
    messageType: [
      WebSocketMessageType.REGENERATION_PROGRESS,
      WebSocketMessageType.REGENERATION_COMPLETE,
      WebSocketMessageType.REGENERATION_ERROR,
    ],
    enabled: isOpen && enableProgressTracking && !!sourceId,
  });

  useEffect(() => {
    if (!lastMessage) return;

    console.log('WebSocket message received:', lastMessage);
    
    if (lastMessage.type === WebSocketMessageType.REGENERATION_PROGRESS) {
      console.log('Progress update:', lastMessage.progress);
      setStatus('processing');
    } else if (lastMessage.type === WebSocketMessageType.REGENERATION_COMPLETE) {
      console.log('Regeneration completed:', lastMessage.result);
      setStatus('completed');
      setResult(lastMessage.result);
    } else if (lastMessage.type === WebSocketMessageType.REGENERATION_ERROR) {
      console.log('Regeneration error:', lastMessage.error);
      setStatus('error');
      setError(lastMessage.error);
    }
  }, [lastMessage]);

  const progress = lastMessage?.progress || null;

  // Reset state when dialog closes
  useEffect(() => {
    if (!isOpen) {
      setShowProgress(false);
      resetWebSocket();
      setStatus('idle');
      setResult(null);
      setError(null);
      setIgnoreHash(false);
    }
  }, [isOpen, resetWebSocket]);

  // Handle Escape key to cancel
  useKeyboardShortcut('Escape', onCancel, isOpen && status !== 'processing');

  if (!isOpen) return null;

  // Default configurations based on type
  const getDefaultConfig = () => {
    switch (type) {
      case 'recrawl':
        return {
          title: title || 'Recrawl Source',
          message: message || 'This will recrawl the source using the same settings:',
          confirmText: confirmText || 'Start Recrawl',
          icon: <RefreshCw className="h-5 w-5" />,
          variant: 'default' as const,
        };
      case 'regenerate':
        return {
          title: title || 'Regenerate Descriptions',
          message: message || `Regenerate LLM-generated titles and descriptions for all ${itemCount || 0} code snippets in "${sourceName}"? This will use your configured LLM to improve metadata quality.`,
          confirmText: confirmText || 'Regenerate',
          icon: <Sparkles className="h-5 w-5" />,
          variant: 'default' as const,
        };
      case 'delete':
        return {
          title: title || 'Confirm Delete',
          message: message || `Are you sure you want to delete the source "${sourceName}"? This will permanently remove all ${itemCount || 0} documents and ${itemCount || 0} code snippets.`,
          confirmText: confirmText || 'Delete',
          icon: <Trash2 className="h-5 w-5" />,
          variant: 'destructive' as const,
        };
      case 'retry':
        return {
          title: title || 'Confirm Retry',
          message: message || `Are you sure you want to retry ${itemCount || 0} failed page(s)?`,
          confirmText: confirmText || 'Retry',
          icon: <RefreshCw className="h-5 w-5" />,
          variant: 'default' as const,
        };
      default:
        return {
          title: title || 'Confirm Action',
          message: message || 'Are you sure you want to proceed?',
          confirmText: confirmText || 'Confirm',
          icon: customIcon || <RefreshCw className="h-5 w-5" />,
          variant: variant,
        };
    }
  };

  const config = getDefaultConfig();

  const handleConfirm = async () => {
    if (type === 'regenerate' && enableProgressTracking && sourceId) {
      setShowProgress(true);
      setStatus('processing');
      
      // Ensure WebSocket is connected and subscribed before starting
      if (!isConnected) {
        console.warn('WebSocket not connected, progress updates may be missed');
      }
      
      // Small delay to ensure subscription message is processed
      await new Promise(resolve => setTimeout(resolve, 100));
      
      onConfirm();
      return;
    }
    
    if (type === 'recrawl' && showForceRegenerateOption) {
      onConfirm({ ignoreHash });
    } else {
      onConfirm();
    }
  };

  const handleClose = () => {
    if (status === 'completed' && result) {
      window.location.reload();
    }
    onCancel();
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'processing':
        return <Loader2 className="h-5 w-5 animate-spin" />;
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return config.icon;
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-background rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <h2 className="text-xl font-semibold">
              {showProgress ? 'Regenerating Descriptions' : config.title}
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground"
            disabled={status === 'processing'}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Show progress if regeneration is in progress */}
          {showProgress ? (
            <>
              <div>
                <p className="text-sm text-muted-foreground mb-2">
                  Regenerating LLM-generated titles and descriptions for source:
                </p>
                <div className="bg-secondary/50 rounded-md p-3">
                  <p className="text-sm font-medium">{sourceName}</p>
                </div>
              </div>

              {progress && (
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Progress</span>
                      <span>{Math.round(progress.percentage)}%</span>
                    </div>
                    <div className="w-full bg-secondary rounded-full h-2">
                      <div 
                        className="bg-primary h-2 rounded-full transition-all duration-300"
                        style={{ width: `${progress.percentage}%` }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="text-center">
                      <p className="font-medium">{progress.processed_snippets}</p>
                      <p className="text-xs text-muted-foreground">Processed</p>
                    </div>
                    <div className="text-center">
                      <p className="font-medium text-green-600">{progress.changed_snippets}</p>
                      <p className="text-xs text-muted-foreground">Changed</p>
                    </div>
                    <div className="text-center">
                      <p className="font-medium text-red-600">{progress.failed_snippets}</p>
                      <p className="text-xs text-muted-foreground">Failed</p>
                    </div>
                  </div>

                  {progress.current_snippet && (
                    <div className="text-xs text-muted-foreground">
                      Currently processing: <span className="font-medium">{progress.current_snippet}</span>
                    </div>
                  )}
                </div>
              )}

              {!progress && status === 'processing' && (
                <div className="text-center py-4">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    {isConnected ? 'Waiting for progress updates...' : 'Processing regeneration...'}
                  </p>
                  {!isConnected && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Real-time progress updates unavailable
                    </p>
                  )}
                </div>
              )}

              {status === 'completed' && result && (
                <div className="p-3 bg-green-500/10 rounded-md">
                  <p className="text-sm text-green-700 dark:text-green-300">
                    Successfully regenerated {result.changed_snippets} of {result.total_snippets} snippets.
                  </p>
                </div>
              )}

              {status === 'error' && error && (
                <div className="p-3 bg-red-500/10 rounded-md">
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {error}
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <div>
                <p className="text-sm text-muted-foreground mb-2">
                  {config.message}
                </p>
                
                {type === 'recrawl' && sourceName && sourceUrl && (
                  <div className="bg-secondary/50 rounded-md p-3 space-y-1">
                    <p className="text-sm">
                      <span className="font-medium">Source:</span> {sourceName}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Base URL:</span> {sourceUrl}
                    </p>
                  </div>
                )}
              </div>

              {type === 'recrawl' && showForceRegenerateOption && (
                <div className="space-y-3">
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={ignoreHash}
                      onChange={(e) => setIgnoreHash(e.target.checked)}
                      className="mt-1"
                      disabled={isConfirming}
                    />
                    <div>
                      <p className="font-medium text-sm">
                        Force regenerate all content
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Ignore content hash and regenerate all LLM descriptions even if the page content hasn&apos;t changed.
                      </p>
                    </div>
                  </label>

                  {ignoreHash && (
                    <div className="flex items-start gap-2 p-3 bg-yellow-500/10 rounded-md">
                      <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5" />
                      <p className="text-xs text-yellow-700 dark:text-yellow-300">
                        This will regenerate all code snippets and descriptions, which may take significantly longer and use more LLM credits.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex gap-3 p-6 border-t border-border">
          <button
            onClick={handleClose}
            disabled={status === 'processing'}
            className="flex-1 px-4 py-2 text-sm border border-input rounded-md hover:bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === 'processing' ? 'Cancel' : 'Close'}
          </button>
          {!showProgress && (
            <button
              onClick={handleConfirm}
              disabled={isConfirming}
              className={`flex-1 px-4 py-2 text-sm rounded-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${
                config.variant === 'destructive'
                  ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              }`}
            >
              {isConfirming ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  {config.icon}
                  {config.confirmText}
                </>
              )}
            </button>
          )}
          {status === 'completed' && (
            <button
              onClick={() => window.location.reload()}
              className="flex-1 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Refresh Data
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
