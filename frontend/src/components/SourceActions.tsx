import { Trash2, Sparkles } from 'lucide-react';
import { ConfirmationDialog } from './ConfirmationDialog';

interface SourceActionsProps {
  source: any;
  deleteModalOpen: boolean;
  deleteMatchesModalOpen: boolean;
  regenerateModalOpen: boolean;
  deleteMutation: any;
  deleteMatchesMutation: any;
  regenerateMutation: any;
  setDeleteModalOpen: (open: boolean) => void;
  setDeleteMatchesModalOpen: (open: boolean) => void;
  setRegenerateModalOpen: (open: boolean) => void;
  handleConfirmDelete: () => void;
  handleConfirmRegenerate: () => void;
}

export function SourceActions({
  source,
  deleteModalOpen,
  deleteMatchesModalOpen,
  regenerateModalOpen,
  deleteMutation,
  deleteMatchesMutation,
  regenerateMutation,
  setDeleteModalOpen,
  setDeleteMatchesModalOpen,
  setRegenerateModalOpen,
  handleConfirmDelete,
  handleConfirmRegenerate,
}: SourceActionsProps) {
  return (
    <>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setRegenerateModalOpen(true)}
          className="flex items-center px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-primary/10"
        >
          <Sparkles className="h-4 w-4 mr-1.5" />
          Regenerate Descriptions
        </button>
        <button
          onClick={() => setDeleteModalOpen(true)}
          className="flex items-center px-3 py-1.5 text-sm text-destructive border border-destructive rounded-md hover:bg-destructive/10"
        >
          <Trash2 className="h-4 w-4 mr-1.5" />
          Delete Source
        </button>
      </div>

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

      <ConfirmationDialog
        isOpen={regenerateModalOpen}
        title="Regenerate Descriptions"
        message={`Regenerate LLM-generated titles and descriptions for all ${source.snippets_count} code snippets in "${source.name}"? This will use your configured LLM to improve metadata quality.`}
        confirmText="Regenerate"
        cancelText="Cancel"
        variant="default"
        isConfirming={regenerateMutation.isPending}
        onConfirm={handleConfirmRegenerate}
        onCancel={() => setRegenerateModalOpen(false)}
      />

    </>
  );
}