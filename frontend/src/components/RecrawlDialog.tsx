import { useState } from "react";
import { X } from "lucide-react";

interface RecrawlDialogProps {
  isOpen: boolean;
  sourceName: string;
  onConfirm: (options: { 
    forceRegenerate: boolean; 
    llmModel?: string;
    llmApiKey?: string;
    llmBaseUrl?: string;
  }) => void;
  onCancel: () => void;
  isRecrawling?: boolean;
}

export function RecrawlDialog({
  isOpen,
  sourceName,
  onConfirm,
  onCancel,
  isRecrawling = false,
}: RecrawlDialogProps) {
  const [forceRegenerate, setForceRegenerate] = useState(false);
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [customModel, setCustomModel] = useState("");
  const [customApiKey, setCustomApiKey] = useState("");
  const [customBaseUrl, setCustomBaseUrl] = useState("");

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (useCustomModel) {
      onConfirm({
        forceRegenerate,
        llmModel: customModel,
        llmApiKey: customApiKey,
        llmBaseUrl: customBaseUrl || undefined,
      });
    } else {
      onConfirm({
        forceRegenerate,
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative bg-background rounded-lg shadow-lg w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Recrawl Source</h2>
          <button
            onClick={onCancel}
            className="p-1 hover:bg-secondary rounded"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Recrawl "<span className="font-medium">{sourceName}</span>" to update documentation and code snippets.
          </p>

          <div className="space-y-3">
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={forceRegenerate}
                onChange={(e) => setForceRegenerate(e.target.checked)}
                className="mt-1"
              />
              <div>
                <div className="font-medium text-sm">Force regenerate metadata</div>
                <div className="text-xs text-muted-foreground">
                  Regenerate all titles, descriptions, and language detection even if content hasn't changed. 
                  This will take longer but can improve quality.
                </div>
              </div>
            </label>

            {forceRegenerate && (
              <div className="ml-6 space-y-3 border-l-2 border-secondary pl-4">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={useCustomModel}
                    onChange={(e) => setUseCustomModel(e.target.checked)}
                    className="mt-1"
                  />
                  <div>
                    <div className="font-medium text-sm">Use custom LLM configuration</div>
                    <div className="text-xs text-muted-foreground">
                      Specify custom model, API key, and endpoint for regeneration
                    </div>
                  </div>
                </label>

                {useCustomModel && (
                  <div className="space-y-3 ml-6 border-l-2 border-secondary pl-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Model Name*</label>
                      <input
                        type="text"
                        value={customModel}
                        onChange={(e) => setCustomModel(e.target.value)}
                        placeholder="e.g., gpt-4, claude-3-opus-20240229"
                        className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">API Key*</label>
                      <input
                        type="password"
                        value={customApiKey}
                        onChange={(e) => setCustomApiKey(e.target.value)}
                        placeholder="sk-..."
                        className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Base URL (Optional)</label>
                      <input
                        type="text"
                        value={customBaseUrl}
                        onChange={(e) => setCustomBaseUrl(e.target.value)}
                        placeholder="https://api.openai.com/v1"
                        className="w-full px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                      <p className="text-xs text-muted-foreground">
                        Leave empty for OpenAI. For other providers, enter their API endpoint.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {forceRegenerate && (
            <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-md">
              <p className="text-xs text-yellow-600 dark:text-yellow-400">
                <strong>Note:</strong> Force regeneration will process all pages regardless of changes. 
                This may take significantly longer depending on the source size.
              </p>
            </div>
          )}
        </div>

        <div className="flex gap-2 p-4 border-t">
          <button
            onClick={onCancel}
            disabled={isRecrawling}
            className="flex-1 px-4 py-2 text-sm border border-input rounded-md hover:bg-secondary disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isRecrawling || (useCustomModel && (!customModel || !customApiKey))}
            className="flex-1 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {isRecrawling ? "Recrawling..." : "Start Recrawl"}
          </button>
        </div>
      </div>
    </div>
  );
}