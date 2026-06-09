"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { CaretLeftIcon, CaretRightIcon, CaretDownIcon } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { DOMAINS, type DomainConfig, type DomainId } from "../../types";

interface DomainSkillPickerProps {
  selectedDomain: DomainId | null;
  onDomainSelect: (domain: DomainId | null) => void;
}

function DomainChip({
  domain,
  isSelected,
  onClick,
}: {
  domain: DomainConfig;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm font-medium transition-all duration-150",
        isSelected
          ? "border-zinc-800 bg-zinc-900 text-white shadow-sm"
          : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-800",
      )}
    >
      <span className="text-base leading-none">{domain.icon}</span>
      <span>{domain.label}</span>
    </motion.button>
  );
}

export function DomainSkillPicker({
  selectedDomain,
  onDomainSelect,
}: DomainSkillPickerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateScrollState();
    el.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState);
    return () => {
      el.removeEventListener("scroll", updateScrollState);
      window.removeEventListener("resize", updateScrollState);
    };
  }, [updateScrollState]);

  function scroll(direction: "left" | "right") {
    const el = scrollRef.current;
    if (!el) return;
    const amount = 200;
    el.scrollBy({ left: direction === "left" ? -amount : amount, behavior: "smooth" });
  }

  function handleChipClick(domain: DomainConfig) {
    if (selectedDomain === domain.id) {
      onDomainSelect(null);
    } else {
      onDomainSelect(domain.id);
    }
  }

  return (
    <div className="relative mb-1 mt-2">
      {/* Left fade + arrow */}
      {canScrollLeft && (
        <>
          <div className="pointer-events-none absolute left-0 top-0 z-10 h-full w-10 bg-gradient-to-r from-zinc-50 to-transparent" />
          <button
            type="button"
            onClick={() => scroll("left")}
            className="absolute -left-1 top-1/2 z-20 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-zinc-200 transition-colors hover:bg-zinc-100"
            aria-label="Scroll left"
          >
            <CaretLeftIcon className="h-4 w-4 text-zinc-500" />
          </button>
        </>
      )}

      {/* Right fade + arrow */}
      {canScrollRight && (
        <>
          <div className="pointer-events-none absolute right-0 top-0 z-10 h-full w-10 bg-gradient-to-l from-zinc-50 to-transparent" />
          <button
            type="button"
            onClick={() => scroll("right")}
            className="absolute -right-1 top-1/2 z-20 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-zinc-200 transition-colors hover:bg-zinc-100"
            aria-label="Scroll right"
          >
            <CaretRightIcon className="h-4 w-4 text-zinc-500" />
          </button>
        </>
      )}

      {/* Chips container */}
      <div
        ref={scrollRef}
        className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide"
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {DOMAINS.map((domain) => (
          <DomainChip
            key={domain.id}
            domain={domain}
            isSelected={selectedDomain === domain.id}
            onClick={() => handleChipClick(domain)}
          />
        ))}
      </div>
    </div>
  );
}
