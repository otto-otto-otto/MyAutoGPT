"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListWorkspaceFiles,
  useDeleteWorkspaceFile,
  useRenameWorkspaceFile,
  getListWorkspaceFilesQueryKey,
} from "@/app/api/__generated__/endpoints/workspace/workspace";
import type { WorkspaceFileItem } from "@/app/api/__generated__/models/workspaceFileItem";
import { useWorkspaceStorage } from "../UsageLimits/useWorkspaceStorage";

const PAGE_SIZE = 20;

export function useFileManager() {
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const storage = useWorkspaceStorage();

  const {
    data: listData,
    isLoading,
    error,
    refetch,
  } = useListWorkspaceFiles(
    { limit: PAGE_SIZE, offset },
    {
      query: {
        select: (res) => (res.status === 200 ? res.data : undefined),
      },
    },
  );

  const files: WorkspaceFileItem[] = listData?.files ?? [];
  const hasMore = listData?.has_more ?? false;
  const totalOffset = listData?.offset ?? offset;

  const deleteMutation = useDeleteWorkspaceFile({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListWorkspaceFilesQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: ["/api/workspace/storage/usage"],
        });
      },
    },
  });

  const renameMutation = useRenameWorkspaceFile({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListWorkspaceFilesQueryKey(),
        });
      },
    },
  });

  const downloadFile = useCallback(async (file: WorkspaceFileItem) => {
    try {
      const response = await fetch(
        `/api/proxy/api/workspace/files/${file.id}/download`,
      );
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download error:", err);
      throw err;
    }
  }, []);

  const deleteFile = useCallback(
    async (fileId: string) => {
      await deleteMutation.mutateAsync({ fileId });
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(fileId);
        return next;
      });
    },
    [deleteMutation],
  );

  const deleteSelected = useCallback(async () => {
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(
      ids.map((fileId) => deleteMutation.mutateAsync({ fileId })),
    );
    const failed = results.filter((r) => r.status === "rejected").length;
    setSelectedIds(new Set());
    return { total: ids.length, failed };
  }, [selectedIds, deleteMutation]);

  const renameFile = useCallback(
    async (fileId: string, newName: string) => {
      return renameMutation.mutateAsync({ fileId, data: { name: newName } });
    },
    [renameMutation],
  );

  const toggleSelect = useCallback((fileId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(files.map((f) => f.id)));
  }, [files]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const isAllSelected =
    files.length > 0 && selectedIds.size === files.length;

  const nextPage = useCallback(() => {
    if (hasMore) setOffset((prev) => prev + PAGE_SIZE);
  }, [hasMore]);

  const prevPage = useCallback(() => {
    setOffset((prev) => Math.max(0, prev - PAGE_SIZE));
  }, []);

  return {
    files,
    isLoading,
    error,
    refetch,
    storage,
    hasMore,
    offset,
    pageSize: PAGE_SIZE,
    selectedIds,
    isAllSelected,
    isDeleting: deleteMutation.isPending,
    isRenaming: renameMutation.isPending,
    downloadFile,
    deleteFile,
    deleteSelected,
    renameFile,
    toggleSelect,
    selectAll,
    clearSelection,
    nextPage,
    prevPage,
  };
}
