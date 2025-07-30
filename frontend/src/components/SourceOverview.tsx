import {  FileText, Code, Calendar, Search } from "lucide-react";
import { Link } from "react-router-dom";

interface SourceOverviewProps {
  source: {
    id: string;
    name: string;
    base_url: string;
    created_at: string;
    documents_count: number;
    snippets_count: number;
  };
}

export function SourceOverview({ source }: SourceOverviewProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-background rounded-md p-4">
          <div className="flex items-center text-muted-foreground mb-1">
            <FileText className="h-4 w-4 mr-2" />
            <span className="text-sm">Documents</span>
          </div>
          <p className="text-2xl font-semibold">
            {source.documents_count}
          </p>
        </div>

        <div className="bg-background rounded-md p-4">
          <div className="flex items-center text-muted-foreground mb-1">
            <Code className="h-4 w-4 mr-2" />
            <span className="text-sm">Code Snippets</span>
          </div>
          <p className="text-2xl font-semibold">
            {source.snippets_count}
          </p>
        </div>

        <div className="bg-background rounded-md p-4">
          <div className="flex items-center text-muted-foreground mb-1">
            <Calendar className="h-4 w-4 mr-2" />
            <span className="text-sm">Created</span>
          </div>
          <p className="text-sm font-medium">
            {new Date(source.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      <Link
        to={`/search?source=${encodeURIComponent(source.name)}`}
        className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
      >
        <Search className="h-4 w-4 mr-2" />
        Search all snippets from this source
      </Link>
    </div>
  );
}