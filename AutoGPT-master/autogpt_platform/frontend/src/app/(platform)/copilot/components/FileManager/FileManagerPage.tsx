"use client";

import { useState } from "react";
import Link from "next/link";
import type { WorkspaceFileItem } from "@/app/api/__generated__/models/workspaceFileItem";
import {
  ArrowLeft,
  Trash,
  DownloadSimple,
  PencilSimple,
  CheckSquare,
  Square,
  CaretLeft,
  CaretRight,
  FolderOpen,
  ArrowsClockwise,
  TrashSimple,
} from "@phosphor-icons/react";
import { Button } from "@/components/atoms/Button/Button";
import { Text } from "@/components/atoms/Text/Text";
import { useFileManager } from "./useFileManager";
import { formatBytes } from "../usageHelpers";
import { FileRow } from "./FileRow";
import { RenameFileDialog } from "./RenameFileDialog";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import { FileTableHeader } from "./FileTableHeader";
import { useToast } from "@/components/molecules/Toast/use-toast";

export function FileManagerPage() {
  const {
    files,
    isLoading,
    error,
    refetch,
    storage,
    hasMore,
    offset,
    pageSize,
    selectedIds,
    isAllSelected,
    isDeleting,
    downloadFile,
    deleteFile,
    deleteSelected,
    renameFile,
    toggleSelect,
    selectAll,
    clearSelection,
    nextPage,
    prevPage,
  } = useFileManager();

  const { toast } = useToast();

  const [renameTarget, setRenameTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    ids: string[];
    names: string[];
  } | null>(null);
  const [batchDeleteMode, setBatchDeleteMode] = useState(false);

  const handleDeleteClick = (fileId: string, fileName: string) => {
    setDeleteTarget({ ids: [fileId], names: [fileName] });
  };

  const handleDownload = async (file: WorkspaceFileItem) => {
    try {
      await downloadFile(file);
      toast({ title: "Download started", description: file.name });
    } catch {
      toast({
        title: "Download failed",
        description: `Could not download ${file.name}`,
        variant: "destructive",
      });
    }
  };

  const handleBatchDeleteClick = () => {
    const selectedFiles = files.filter((f) => selectedIds.has(f.id));
    setDeleteTarget({
      ids: selectedFiles.map((f) => f.id),
      names: selectedFiles.map((f) => f.name),
    });
  };

  const handleConfirmDelete = () => {
    if (!deleteTarget) return;

    if (deleteTarget.ids.length === 1) {
      deleteFile(deleteTarget.ids[0]);
      toast({ title: "File deleted", description: deleteTarget.names[0] });
    } else {
      deleteSelected().then((result) => {
        toast({
          title: `${result.total - result.failed} files deleted`,
          description:
            result.failed > 0
              ? `${result.failed} files failed to delete`
              : undefined,
          variant: result.failed > 0 ? "destructive" : undefined,
        });
      });
    }
    setDeleteTarget(null);
  };

  const handleRename = async (name: string) => {
    if (!renameTarget) return;

    const result = await renameFile(renameTarget.id, name);
    if (result.status === 200) {
      toast({ title: "Renamed to", description: name });
    } else if (result.status === 409) {
      toast({
        title: "Name conflict",
        description: "A file with this name already exists",
        variant: "destructive",
      });
    }
    setRenameTarget(null);
  };

  const currentPage = Math.floor(offset / pageSize) + 1;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 pb-20 pt-8 sm:px-8 md:px-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/copilot">
            <Button variant="ghost" size="small" leftIcon={<ArrowLeft />}>
              Copilot
            </Button>
          </Link>
          <Text variant="h4">Workspace Files</Text>
        </div>
        <Button
          variant="ghost"
          size="small"
          leftIcon={<ArrowsClockwise />}
          onClick={() => refetch()}
        >
          Refresh
        </Button>
      </div>

      {/* Storage bar */}
      {storage.data && storage.data.limit_bytes > 0 && (
        <div className="rounded-xl border border-neutral-200 bg-white p-4">
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <Text variant="body-medium" className="text-neutral-700">
                File storage
              </Text>
              <Text variant="body" className="tabular-nums text-neutral-500">
                {Math.round(
                  (storage.data.used_bytes / storage.data.limit_bytes) * 100,
                )}
                % used
              </Text>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-200">
              <div
                role="progressbar"
                aria-label="File storage usage"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(
                  (storage.data.used_bytes / storage.data.limit_bytes) * 100,
                )}
                className={`h-full rounded-full transition-[width] duration-300 ease-out ${
                  storage.data.used_bytes / storage.data.limit_bytes >= 0.8
                    ? "bg-orange-500"
                    : "bg-blue-500"
                }`}
                style={{
                  width: `${Math.max(
                    storage.data.used_bytes > 0 ? 1 : 0,
                    Math.round(
                      (storage.data.used_bytes / storage.data.limit_bytes) *
                        100,
                    ),
                  )}%`,
                }}
              />
            </div>
            <Text variant="small" className="text-neutral-400">
              {formatBytes(storage.data.used_bytes)} of{" "}
              {formatBytes(storage.data.limit_bytes)} &middot;{" "}
              {storage.data.file_count}{" "}
              {storage.data.file_count === 1 ? "file" : "files"}
            </Text>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 ? (
            <>
              <Text variant="small" className="text-neutral-500">
                {selectedIds.size} selected
              </Text>
              <Button
                variant="destructive"
                size="small"
                leftIcon={<TrashSimple />}
                onClick={handleBatchDeleteClick}
                loading={isDeleting}
              >
                Delete selected
              </Button>
              <Button
                variant="ghost"
                size="small"
                onClick={clearSelection}
              >
                Clear
              </Button>
            </>
          ) : (
            <>
              {files.length > 0 && (
                <Button
                  variant="ghost"
                  size="small"
                  leftIcon={isAllSelected ? <CheckSquare /> : <Square />}
                  onClick={isAllSelected ? clearSelection : selectAll}
                >
                  {isAllSelected ? "Deselect all" : "Select all"}
                </Button>
              )}
            </>
          )}
        </div>
        <Text variant="small" className="text-neutral-400">
          {files.length > 0
            ? `Showing ${offset + 1}–${offset + files.length}`
            : "No files"}
        </Text>
      </div>

      {/* File list */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Text variant="body" className="text-neutral-400">
            Loading files...
          </Text>
        </div>
      )}

      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-4 py-20">
          <Text variant="body" className="text-red-500">
            Failed to load files
          </Text>
          <Button variant="secondary" size="small" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {!isLoading && !error && files.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 py-20">
          <FolderOpen size={48} className="text-neutral-300" />
          <Text variant="body" className="text-neutral-400">
            No files in workspace
          </Text>
          <Text variant="small" className="text-neutral-300">
            Files uploaded during Copilot sessions will appear here
          </Text>
        </div>
      )}

      {!isLoading && !error && files.length > 0 && (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-xl border border-neutral-200 bg-white md:block">
            <FileTableHeader
              isAllSelected={isAllSelected}
              hasSelection={selectedIds.size > 0}
              onSelectAllToggle={isAllSelected ? clearSelection : selectAll}
            />
            <div className="divide-y divide-neutral-100">
              {files.map((file) => (
                <FileRow
                  key={file.id}
                  file={file}
                  isSelected={selectedIds.has(file.id)}
                  onToggleSelect={() => toggleSelect(file.id)}
                  onRename={() =>
                    setRenameTarget({ id: file.id, name: file.name })
                  }
                  onDownload={() => handleDownload(file)}
                  onDelete={() => handleDeleteClick(file.id, file.name)}
                  onOpenFile={() => handleDownload(file)}
                />
              ))}
            </div>
          </div>

          {/* Mobile cards */}
          <div className="space-y-2 md:hidden">
            {files.map((file) => (
              <div
                key={file.id}
                className="rounded-lg border border-neutral-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <button
                      onClick={() => handleDownload(file)}
                      className="truncate text-left font-medium text-neutral-800 hover:text-blue-600 hover:underline cursor-pointer"
                      title={`Open ${file.name}`}
                    >
                      {file.name}
                    </button>
                    <div className="mt-1 flex items-center gap-2">
                      <Text variant="small" className="text-neutral-400">
                        {file.mime_type}
                      </Text>
                      <Text variant="small" className="text-neutral-300">
                        &middot;
                      </Text>
                      <Text variant="small" className="text-neutral-400">
                        {formatBytes(file.size_bytes)}
                      </Text>
                    </div>
                    <Text variant="small" className="mt-1 text-neutral-300">
                      Created: {new Date(file.created_at).toLocaleDateString()}
                    </Text>
                    <Text variant="small" className="mt-0.5 text-neutral-300">
                      Last Modified: {new Date(file.updated_at).toLocaleDateString()}
                    </Text>
                  </div>
                  <div className="flex shrink-0 items-center gap-0">
                    <button
                      onClick={() =>
                        setRenameTarget({ id: file.id, name: file.name })
                      }
                      aria-label="Rename"
                      title="Rename"
                      className="rounded p-1.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800"
                    >
                      <PencilSimple size={16} />
                    </button>
                    <button
                      onClick={() => handleDownload(file)}
                      aria-label="Download"
                      title="Download"
                      className="rounded p-1.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800"
                    >
                      <DownloadSimple size={16} />
                    </button>
                    <button
                      onClick={() => handleDeleteClick(file.id, file.name)}
                      aria-label="Delete"
                      title="Delete"
                      className="rounded p-1.5 text-red-500 transition-colors hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash size={16} className="text-red-500" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="small"
              leftIcon={<CaretLeft />}
              onClick={prevPage}
              disabled={offset === 0}
            >
              Previous
            </Button>
            <Text variant="small" className="tabular-nums text-neutral-400">
              Page {currentPage}
            </Text>
            <Button
              variant="ghost"
              size="small"
              rightIcon={<CaretRight />}
              onClick={nextPage}
              disabled={!hasMore}
            >
              Next
            </Button>
          </div>
        </>
      )}

      {/* Dialogs */}
      {renameTarget && (
        <RenameFileDialog
          fileName={renameTarget.name}
          onSave={handleRename}
          onCancel={() => setRenameTarget(null)}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmDialog
          fileNames={deleteTarget.names}
          onConfirm={handleConfirmDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
}
