import { Search, Trash2, X, Wand2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SnippetList } from "./SnippetList";
import { PaginationControls } from "./PaginationControls";
import { Spinner } from "./Spinner";

interface SourceSnippetsTabProps {
  snippets: any;
  languages: any;
  snippetsLoading: boolean;
  snippetsPage: number;
  selectedLanguage: string;
  snippetsSearch: string;
  debouncedSnippetsSearch: string;
  snippetsPerPage: number;
  snippetsTotalPages: number;
  setSnippetsPage: (page: number) => void;
  setSelectedLanguage: (lang: string) => void;
  setSnippetsSearch: (search: string) => void;
  formatPreviewMutation: any;
  setDeleteMatchesModalOpen: (open: boolean) => void;
}

export function SourceSnippetsTab({
  snippets,
  languages,
  snippetsLoading,
  snippetsPage,
  selectedLanguage,
  snippetsSearch,
  debouncedSnippetsSearch,
  snippetsPerPage,
  snippetsTotalPages,
  setSnippetsPage,
  setSelectedLanguage,
  setSnippetsSearch,
  formatPreviewMutation,
  setDeleteMatchesModalOpen,
}: SourceSnippetsTabProps) {
  return (
    <div className="space-y-4">
      {/* Search and Filter Bar */}
      <div className="flex items-center justify-between mb-4 gap-2">
        <div className="flex gap-3 flex-1">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search code snippets..."
              value={snippetsSearch}
              onChange={(e) => {
                setSnippetsSearch(e.target.value);
              }}
              className="w-full pl-10 pr-4 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {snippetsSearch && (
              <>
                <span className="absolute right-12 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                  {snippets && snippets.total > 0 ? `(${snippets.total} matches)` : '(0 matches)'}
                </span>
                <button
                  onClick={() => {
                    setSnippetsSearch("");
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </>
            )}
          </div>

          {languages && languages.languages.length > 0 && (
            <Select value={selectedLanguage} onValueChange={(value) => {
              setSelectedLanguage(value === "all" ? "" : value);
              setSnippetsPage(1);
            }}>
              <SelectTrigger className="w-[180px] h-[42px]!">
                <SelectValue placeholder="All Languages" />
              </SelectTrigger>
              <SelectContent className="">
                <SelectItem value="all">All Languages</SelectItem>
                {languages.languages.map((lang: any) => (
                  <SelectItem key={lang.name} value={lang.name}>
                    {lang.name} ({lang.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        
        <button
          onClick={() => setDeleteMatchesModalOpen(true)}
          disabled={snippetsLoading || !snippets || snippets.total === 0 || !debouncedSnippetsSearch}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/80 disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px] justify-center h-10 cursor-pointer"
        >
          <Trash2 className="h-4 w-4" />
          Delete Matches
        </button>
        <button
          onClick={() => formatPreviewMutation.mutate()}
          disabled={formatPreviewMutation.isPending || snippetsLoading || !snippets || snippets.total === 0}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed min-w-[120px] justify-center h-10 cursor-pointer"
        >
          {formatPreviewMutation.isPending ? (
            <>
              <Spinner size="sm" className="text-secondary-foreground" />
              Analyzing...
            </>
          ) : (
            <>
              <Wand2 className="h-4 w-4" />
              Format All
            </>
          )}
        </button>
              </div>

      {/* Snippets List */}
      {snippetsLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Searching snippets...
        </div>
      ) : snippets ? (
        <>
          <SnippetList
            snippets={snippets.snippets}
            showSource={false}
          />
          {snippetsTotalPages > 1 && (
            <PaginationControls
              currentPage={snippetsPage}
              totalPages={snippetsTotalPages}
              onPageChange={setSnippetsPage}
              totalItems={snippets.total}
              itemsPerPage={snippetsPerPage}
              currentItemsCount={snippets.snippets.length}
            />
          )}
        </>
      ) : null}
    </div>
  );
}