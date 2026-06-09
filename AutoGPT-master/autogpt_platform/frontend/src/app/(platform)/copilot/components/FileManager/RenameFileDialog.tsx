"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button/Button";
import { Text } from "@/components/atoms/Text/Text";

interface RenameFileDialogProps {
  fileName: string;
  onSave: (newName: string) => void;
  onCancel: () => void;
}

export function RenameFileDialog({
  fileName,
  onSave,
  onCancel,
}: RenameFileDialogProps) {
  const [value, setValue] = useState(fileName);
  const [error, setError] = useState("");

  const handleSave = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("File name cannot be empty");
      return;
    }
    if (trimmed.includes("/") || trimmed.includes("\\")) {
      setError("File name cannot contain path separators");
      return;
    }
    if (trimmed === fileName) {
      onCancel();
      return;
    }
    onSave(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") onCancel();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <Text variant="h5" className="mb-1">
          Rename file
        </Text>
        <Text variant="small" className="mb-4 text-neutral-400">
          Enter a new name for this file
        </Text>

        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError("");
          }}
          onKeyDown={handleKeyDown}
          autoFocus
          className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 ${
            error ? "border-red-400" : "border-neutral-300"
          }`}
          placeholder="File name"
        />
        {error && (
          <Text variant="small" className="mt-1 text-red-500">
            {error}
          </Text>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="small" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" size="small" onClick={handleSave}>
            Rename
          </Button>
        </div>
      </div>
    </div>
  );
}
