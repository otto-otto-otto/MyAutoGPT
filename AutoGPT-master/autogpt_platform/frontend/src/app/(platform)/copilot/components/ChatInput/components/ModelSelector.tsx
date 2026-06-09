"use client";

import { cn } from "@/lib/utils";
import { Cpu } from "@phosphor-icons/react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/molecules/Popover/Popover";
import type {
  CopilotLlmModel,
  CopilotProvider,
  CopilotTier,
} from "../../../store";
import { parseModelString } from "../../../store";
import { useState } from "react";

interface ProviderInfo {
  key: CopilotProvider;
  label: string;
}

const PROVIDERS: ProviderInfo[] = [
  { key: "deepseek", label: "DeepSeek" },
  { key: "qwen", label: "通义千问" },
  { key: "ernie", label: "文心一言" },
];

interface Props {
  model: CopilotLlmModel;
  onSelect: (model: CopilotLlmModel) => void;
}

export function ModelSelector({ model, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const parsed = parseModelString(model);
  const isAdvanced = parsed.tier === "advanced";

  function handleTierToggle() {
    const nextTier: CopilotTier = isAdvanced ? "standard" : "advanced";
    const next: CopilotLlmModel = `${parsed.provider}:${nextTier}` as CopilotLlmModel;
    onSelect(next);
    setOpen(false);
  }

  function handleSelectAndClose(model: CopilotLlmModel) {
    onSelect(model);
    setOpen(false);
  }

  const providerLabel =
    PROVIDERS.find((p) => p.key === parsed.provider)?.label ?? "DeepSeek";
  const tierLabel = isAdvanced ? "Advanced" : "Balanced";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-pressed={isAdvanced}
          className={cn(
            "inline-flex h-9 items-center justify-center gap-1 rounded-full border border-neutral-200 bg-white px-2.5 text-xs font-medium shadow-sm transition-colors hover:bg-neutral-50",
            isAdvanced
              ? "text-sky-900"
              : "text-neutral-500 hover:text-neutral-700",
          )}
          aria-label="Open model selector"
        >
          <Cpu size={14} />
          <span className="hidden sm:inline">
            {providerLabel}: {tierLabel}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-64 p-3"
        align="start"
        sideOffset={8}
      >
        {/* Provider row */}
        <div className="mb-3">
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-neutral-400">
            选择厂商
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {PROVIDERS.map((p) => {
              const selected = parsed.provider === p.key;
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => {
                    const next = `${p.key}:${parsed.tier}` as CopilotLlmModel;
                    handleSelectAndClose(next);
                  }}
                  className={cn(
                    "rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                    selected
                      ? "bg-sky-600 text-white"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
                  )}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Tier toggle */}
        <div>
          <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-neutral-400">
            模型档位
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-xs",
                !isAdvanced ? "font-semibold text-neutral-800" : "text-neutral-400",
              )}
            >
              Balanced
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={isAdvanced}
              onClick={handleTierToggle}
              className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400",
                isAdvanced ? "bg-sky-600" : "bg-neutral-300",
              )}
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
                  isAdvanced ? "translate-x-4" : "translate-x-0",
                )}
              />
            </button>
            <span
              className={cn(
                "text-xs",
                isAdvanced ? "font-semibold text-sky-700" : "text-neutral-400",
              )}
            >
              Advanced
            </span>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
