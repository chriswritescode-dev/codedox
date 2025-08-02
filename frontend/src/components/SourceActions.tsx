import { Trash2 } from 'lucide-react';
import { ConfirmationDialog } from './ConfirmationDialog';
import { FormatSourceDialog } from './FormatSourceDialog';

interface SourceActionsProps {
  source: any;
  deleteModalOpen: boolean;
  deleteMatchesModalOpen: boolean;
  formatDialogOpen: boolean;
  formatPreview: any;
  deleteMutation: any;
  deleteMatchesMutation: any;
  formatSourceMutation: any;
  handleConfirmFormat: () => void;
  setDeleteModalOpen: (open: boolean) => void;
  setDeleteMatchesModalOpen: (open: boolean) => void;
  setFormatDialogOpen: (open: boolean) => void;
  setFormatPreview: (preview: any) => void;
  handleConfirmDelete: () => void;
}

export function SourceActions({
  source,
  deleteModalOpen,
  deleteMatchesModalOpen,
  formatDialogOpen,
  formatPreview,
  deleteMutation,
  deleteMatchesMutation,
  formatSourceMutation,
  handleConfirmFormat,
  setDeleteModalOpen,
  setDeleteMatchesModalOpen,
  setFormatDialogOpen,
  setFormatPreview,
  handleConfirmDelete,
}: SourceActionsProps) {
  return (
    <>
      <button
        onClick={() => setDeleteModalOpen(true)}
        className="flex items-center px-3 py-1.5 text-sm text-destructive border border-destructive rounded-md hover:bg-destructive/10"
      >
        <Trash2 className="h-4 w-4 mr-1.5" />
        Delete Source
      </button>

      <ConfirmationDialog
        isOpen={deleteModalOpen}
        title="Confirm Delete"
        message={`Are you sure you want to delete the source "${source.name}"? This will permanently remove all ${source.documents_count} documents and ${source.snippets_count} code snippets.`}
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteModalOpen(false)}
      />

      <ConfirmationDialog
        isOpen={deleteMatchesModalOpen}
        title="Delete Matches"
        message={`Are you sure you want to delete all snippets matching the current search criteria? This action cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        variant="destructive"
        isConfirming={deleteMatchesMutation.isPending}
        onConfirm={() => deleteMatchesMutation.mutate()}
        onCancel={() => setDeleteMatchesModalOpen(false)}
      />

      {formatPreview && (
        <FormatSourceDialog
          isOpen={formatDialogOpen}
          sourceName={source.name}
          totalSnippets={formatPreview.total_snippets}
          changedSnippets={formatPreview.changed_snippets}
          preview={formatPreview.preview}
          isFormatting={formatSourceMutation.isPending}
          onConfirm={handleConfirmFormat}
          onCancel={() => {
            setFormatDialogOpen(false);
            setFormatPreview(null);
          }}
        />
      )}
    </>
  );
}