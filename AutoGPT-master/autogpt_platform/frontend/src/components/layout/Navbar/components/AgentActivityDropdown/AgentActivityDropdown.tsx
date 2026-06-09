"use client";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/molecules/Popover/Popover";
import { Bell } from "@phosphor-icons/react";
import { formatNotificationCount } from "./helpers";
import { useAgentActivityDropdown } from "./useAgentActivityDropdown";
import { ActivityDropdown } from "./components/ActivityDropdown/ActivityDropdown";

export function AgentActivityDropdown() {
  const {
    activeExecutions,
    recentCompletions,
    recentFailures,
    totalCount,
    isReady,
    isOpen,
    setIsOpen,
  } = useAgentActivityDropdown();

  const hasActivity = isReady && totalCount > 0;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="agent-activity-button"
          className="relative inline-flex items-center justify-center rounded-full p-2 text-zinc-700 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
          aria-label="Agent activity notifications"
        >
          <Bell size={20} weight="regular" />
          {hasActivity ? (
            <span
              data-testid="agent-activity-badge"
              className="absolute -right-0.5 -top-0.5 flex min-w-[18px] items-center justify-center rounded-full bg-purple-500 px-1 py-px text-[10px] font-semibold leading-none text-white"
            >
              {formatNotificationCount(totalCount)}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={8}
        alignOffset={-4}
        className="w-80 overflow-hidden rounded-2xl border border-neutral-200 bg-white p-0 shadow-lg"
      >
        <ActivityDropdown
          activeExecutions={activeExecutions}
          recentCompletions={recentCompletions}
          recentFailures={recentFailures}
        />
      </PopoverContent>
    </Popover>
  );
}
