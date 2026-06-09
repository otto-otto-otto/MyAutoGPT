"use client";

import { Button } from "@/components/atoms/Button/Button";
import { Text } from "@/components/atoms/Text/Text";
import { TrashSimple } from "@phosphor-icons/react";

interface DeleteConfirmDialogProps {
  fileNames: string[];
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

export function DeleteConfirmDialog({
  fileNames,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmDialogProps) {
  const isBatch = fileNames.length > 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
            <TrashSimple size={20} className="text-red-500" />
          </div>
          <div className="min-w-0">
            <Text variant="h5">
              {isBatch ? "Delete selected files" : "Delete file"}
            </Text>
            <Text variant="small" className="mt-1 text-neutral-400">
              {isBatch
                ? `Are you sure you want to delete ${fileNames.length} files? This action cannot be undone.`
                : "Are you sure you want to delete this file? This action cannot be undone."}
            </Text>

            {fileNames.length <= 5 && (
              <div className="mt-3 max-h-32 space-y-1 overflow-y-auto rounded-lg bg-neutral-50 p-3">
                {fileNames.map((name, i) => (
                  <Text
                    key={i}
                    variant="small"
                    className="truncate text-neutral-600"
                  >
                    {name}
                  </Text>
                ))}
              </div>
            )}
            {fileNames.length > 5 && (
              <Text variant="small" className="mt-2 text-neutral-400">
                ...and {fileNames.length - 5} more files
              </Text>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button
            variant="ghost"
            size="small"
            onClick={onCancel}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="small"
            onClick={onConfirm}
            loading={isDeleting}
          >
            {isBatch ? `Delete ${fileNames.length} files` : "Delete"}
          </Button>
        </div>
      </div>
    </div>
  );
}
