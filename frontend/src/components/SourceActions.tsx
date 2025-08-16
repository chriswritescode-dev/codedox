import { Trash2 } from 'lucide-react';
import { ConfirmationDialog } from './ConfirmationDialog';

interface SourceActionsProps {
  source: any;
  deleteModalOpen: boolean;
  deleteMatchesModalOpen: boolean;
  deleteMutation: any;
  deleteMatchesMutation: any;
  setDeleteModalOpen: (open: boolean) => void;
  setDeleteMatchesModalOpen: (open: boolean) => void;
  handleConfirmDelete: () => void;
}

export function SourceActions({
  source,
  deleteModalOpen,
  deleteMatchesModalOpen,
  deleteMutation,
  deleteMatchesMutation,
  setDeleteModalOpen,
  setDeleteMatchesModalOpen,
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

    </>
  );
}