"use client";

import { StoreSubmission } from "@/app/api/__generated__/models/storeSubmission";
import { StoreSubmissionEditRequest } from "@/app/api/__generated__/models/storeSubmissionEditRequest";
import { Dialog } from "@/components/molecules/Dialog/Dialog";
import { EditAgentForm } from "./components/EditAgentForm";

interface EditPayload extends StoreSubmissionEditRequest {
  store_listing_version_id: string | undefined;
  graph_id: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  submission: EditPayload | null;
  onSuccess: (submission: StoreSubmission) => void;
}

export function EditAgentModal({
  isOpen,
  onClose,
  submission,
  onSuccess,
}: Props) {
  if (!submission) {
    return null;
  }

  return (
    <Dialog
      onClose={onClose}
      controlled={{
        isOpen,
        set: async (open) => {
          if (!open) onClose();
        },
      }}
    >
      <Dialog.Content>
        <div
          data-testid="edit-agent-modal"
          className="flex w-full flex-col px-4 pb-4 pt-4 sm:px-6 sm:pb-6 sm:pt-6"
        >
          <EditAgentForm
            submission={submission}
            onClose={onClose}
            onSuccess={onSuccess}
          />
        </div>
      </Dialog.Content>
    </Dialog>
  );
}
