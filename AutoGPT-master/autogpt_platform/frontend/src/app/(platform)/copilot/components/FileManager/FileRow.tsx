"use client";

import {
  Trash,
  DownloadSimple,
  PencilSimple,
  File as FileIcon,
  FileImage,
  FileVideo,
  FileAudio,
  FileText,
  FileCode,
  FilePdf,
  FileArchive,
} from "@phosphor-icons/react";
import { type WorkspaceFileItem } from "@/app/api/__generated__/models/workspaceFileItem";
import { Text } from "@/components/atoms/Text/Text";
import { formatBytes } from "../usageHelpers";

function getFileIcon(mimeType: string) {
  if (mimeType.startsWith("image/")) return FileImage;
  if (mimeType.startsWith("video/")) return FileVideo;
  if (mimeType.startsWith("audio/")) return FileAudio;
  if (mimeType.startsWith("text/")) return FileText;
  if (mimeType.includes("pdf")) return FilePdf;
  if (
    mimeType.includes("zip") ||
    mimeType.includes("tar") ||
    mimeType.includes("gzip") ||
    mimeType.includes("rar") ||
    mimeType.includes("7z")
  )
    return FileArchive;
  if (
    mimeType.includes("javascript") ||
    mimeType.includes("json") ||
    mimeType.includes("xml") ||
    mimeType.includes("html") ||
    mimeType.includes("css") ||
    mimeType.includes("python") ||
    mimeType.includes("code")
  )
    return FileCode;
  return FileIcon;
}

function getFileTypeLabel(mimeType: string): string {
  if (mimeType.startsWith("image/")) return "Image";
  if (mimeType.startsWith("video/")) return "Video";
  if (mimeType.startsWith("audio/")) return "Audio";
  if (mimeType.startsWith("text/")) return "Text";
  if (mimeType.includes("pdf")) return "PDF";
  if (mimeType.includes("zip") || mimeType.includes("tar") || mimeType.includes("gzip") || mimeType.includes("rar")) return "Archive";
  if (mimeType.includes("javascript") || mimeType.includes("json")) return "Code";
  if (mimeType === "application/octet-stream") return "Binary";
  return mimeType.split("/")[1] || mimeType;
}

interface FileRowProps {
  file: WorkspaceFileItem;
  isSelected: boolean;
  onToggleSelect: () => void;
  onRename: () => void;
  onDownload: () => void;
  onDelete: () => void;
  onOpenFile: () => void;
}

export function FileRow({
  file,
  isSelected,
  onToggleSelect,
  onRename,
  onDownload,
  onDelete,
  onOpenFile,
}: FileRowProps) {
  const Icon = getFileIcon(file.mime_type);
  const typeLabel = getFileTypeLabel(file.mime_type);
  const createdDate = new Date(file.created_at);
  const updatedDate = new Date(file.updated_at);

  return (
    <div className="flex items-center gap-3 px-6 py-3 transition-colors hover:bg-neutral-50">
      {/* Checkbox */}
      <button
        onClick={onToggleSelect}
        className="shrink-0 text-neutral-400 hover:text-blue-500"
        title={isSelected ? "Deselect" : "Select"}
      >
        <div
          className={`flex h-5 w-5 items-center justify-center rounded border-2 transition-colors ${
            isSelected
              ? "border-blue-500 bg-blue-500 text-white"
              : "border-neutral-300 bg-white"
          }`}
        >
          {isSelected && (
            <svg
              className="h-3 w-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={3}
                d="M5 13l4 4L19 7"
              />
            </svg>
          )}
        </div>
      </button>

      {/* File info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Icon size={18} className="shrink-0 text-neutral-400" />
          <button
            onClick={onOpenFile}
            className="truncate text-left text-neutral-800 hover:text-blue-600 hover:underline cursor-pointer"
            title={`Open ${file.name}`}
          >
            {file.name}
          </button>
        </div>
        <Text variant="small" className="mt-0.5 text-neutral-400 md:hidden">
          {typeLabel} &middot; {formatBytes(file.size_bytes)}
        </Text>
      </div>

      {/* Size (desktop) */}
      <div className="hidden w-20 text-left md:block">
        <Text variant="small" className="tabular-nums text-neutral-500">
          {formatBytes(file.size_bytes)}
        </Text>
      </div>

      {/* Date (desktop) */}
      <div className="hidden w-36 text-left md:block">
        <Text variant="small" className="tabular-nums text-neutral-400">
          {createdDate.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </Text>
      </div>

      {/* Modified (desktop) */}
      <div className="hidden w-36 text-left md:block">
        <Text variant="small" className="tabular-nums text-neutral-400">
          {updatedDate.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </Text>
      </div>

      {/* Actions */}
      <div className="flex shrink-0 items-center justify-end gap-0">
        <button
          onClick={onRename}
          aria-label="Rename"
          title="Rename"
          className="rounded p-1.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800"
        >
          <PencilSimple size={16} />
        </button>
        <button
          onClick={onDownload}
          aria-label="Download"
          title="Download"
          className="rounded p-1.5 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800"
        >
          <DownloadSimple size={16} />
        </button>
        <button
          onClick={onDelete}
          aria-label="Delete"
          title="Delete"
          className="rounded p-1.5 text-red-500 transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <Trash size={16} className="text-red-500" />
        </button>
      </div>
    </div>
  );
}
