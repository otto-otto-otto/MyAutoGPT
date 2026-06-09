"use client";

import { Minus, Square, CheckSquare } from "@phosphor-icons/react";
import { Text } from "@/components/atoms/Text/Text";

interface FileTableHeaderProps {
  isAllSelected: boolean;
  hasSelection: boolean;
  onSelectAllToggle: () => void;
}

export function FileTableHeader({
  isAllSelected,
  hasSelection,
  onSelectAllToggle,
}: FileTableHeaderProps) {
  const Icon = isAllSelected ? CheckSquare : hasSelection ? Minus : Square;

  return (
    <div className="flex items-center gap-3 border-b border-neutral-200 bg-neutral-50 px-6 py-3">
      <button
        onClick={onSelectAllToggle}
        className="text-neutral-400 hover:text-neutral-600"
        title={isAllSelected ? "Deselect all" : "Select all"}
      >
        <Icon size={18} weight={isAllSelected ? "fill" : "regular"} />
      </button>
      <div className="min-w-0 flex-1">
        <Text variant="small" className="font-medium text-neutral-500">
          Name
        </Text>
      </div>
      <div className="hidden w-20 text-left md:block">
        <Text variant="small" className="font-medium text-neutral-500">
          Size
        </Text>
      </div>
      <div className="hidden w-36 text-left md:block">
        <Text variant="small" className="font-medium text-neutral-500">
          Created
        </Text>
      </div>
      <div className="hidden w-36 text-left md:block">
        <Text variant="small" className="font-medium text-neutral-500">
          Last Modified
        </Text>
      </div>
      <div className="w-24" />
    </div>
  );
}
