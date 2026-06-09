"use client";

import { Button } from "@/components/atoms/Button/Button";
import { cn } from "@/lib/utils";
import { XIcon } from "@phosphor-icons/react";
import { useCopilotUIStore, VERTICAL_DOMAINS } from "../../store";
import type { DomainId } from "../../store";

interface Props {
  className?: string;
}

/**
 * Horizontal scrollable chip selector for vertical-domain skills.
 * Rendered in Copilot's EmptySession (new chat) and above ChatInput (active session).
 * Selecting a domain injects its system prompt as `context` in stream requests.
 */
export function VerticalSkillPicker({ className }: Props) {
  const selectedDomain = useCopilotUIStore((s) => s.selectedDomain);
  const setSelectedDomain = useCopilotUIStore((s) => s.setSelectedDomain);

  function handleToggle(domainId: DomainId) {
    if (selectedDomain === domainId) {
      setSelectedDomain(null); // deselect
    } else {
      setSelectedDomain(domainId);
    }
  }

  function handleClear() {
    setSelectedDomain(null);
  }

  if (VERTICAL_DOMAINS.length === 0) return null;

  return (
    <div className={cn("flex items-center justify-center gap-2", className)}>
      <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none sm:flex-wrap sm:justify-center">
        {VERTICAL_DOMAINS.map((domain) => {
          const isSelected = selectedDomain === domain.id;
          return (
            <Button
              key={domain.id}
              type="button"
              variant={isSelected ? "primary" : "outline"}
              size="small"
              onClick={() => handleToggle(domain.id)}
              className={cn(
                "shrink-0 gap-1 rounded-full px-3 py-1 text-xs font-medium transition-all",
                isSelected
                  ? "bg-violet-600 text-white hover:bg-violet-700"
                  : "border-zinc-200 bg-white text-zinc-600 hover:border-violet-300 hover:text-violet-600",
              )}
            >
              <span className="text-sm leading-none">{domain.icon}</span>
              <span>{domain.label}</span>
            </Button>
          );
        })}
      </div>
      {selectedDomain && (
        <Button
          type="button"
          variant="ghost"
          size="small"
          onClick={handleClear}
          className="shrink-0 rounded-full px-2 text-zinc-400 hover:text-zinc-600"
          aria-label="Clear selected skill"
        >
          <XIcon size={14} weight="bold" />
        </Button>
      )}
    </div>
  );
}
