import { memo } from "react";
import { SourcesContent } from "../components/sources/SourcesContent";

const SourcesHeader = memo(function SourcesHeader() {
  return (
    <div className="pb-4">
      <h1 className="text-3xl font-bold">Documentation Sources</h1>
    </div>
  );
});

export default function Sources() {
  return (
    <div className="flex flex-col h-full w-full min-h-0">
      <SourcesHeader />
      <SourcesContent />
    </div>
  );
}
