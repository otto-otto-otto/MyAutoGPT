"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { HeartIcon, ListIcon } from "@phosphor-icons/react";
import { LibraryActionHeader } from "./components/LibraryActionHeader/LibraryActionHeader";
import { LibraryAgentList } from "./components/LibraryAgentList/LibraryAgentList";
import { DomainSkillPicker } from "./components/DomainSkillPicker/DomainSkillPicker";
import { useLibraryListPage } from "./components/useLibraryListPage";
import { FavoriteAnimationProvider } from "./context/FavoriteAnimationContext";
import type { LibraryTab, AgentStatusFilter, DomainId } from "./types";
import { DOMAIN_GRAPH_ID_MAP } from "./types";
import { useLibraryFleetSummary } from "./hooks/useLibraryFleetSummary";
import { Flag, useGetFlag } from "@/services/feature-flags/use-get-flag";
import { useLibraryAgents } from "@/hooks/useLibraryAgents/useLibraryAgents";

const LIBRARY_TABS: LibraryTab[] = [
  { id: "all", title: "All", icon: ListIcon },
  { id: "favorites", title: "Favorites", icon: HeartIcon },
];

export default function LibraryPage() {
  const { searchTerm, setSearchTerm, librarySort, setLibrarySort } =
    useLibraryListPage();
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(LIBRARY_TABS[0].id);
  const [statusFilter, setStatusFilter] = useState<AgentStatusFilter>("all");
  const [selectedDomain, setSelectedDomain] = useState<DomainId | null>(null);
  const isAgentBriefingEnabled = useGetFlag(Flag.AGENT_BRIEFING);
  const { agents } = useLibraryAgents();

  const filteredAgents = useMemo(() => {
    if (!selectedDomain) return agents;
    const targetGraphId = DOMAIN_GRAPH_ID_MAP[selectedDomain];
    return agents.filter((agent) => agent.graph_id === targetGraphId);
  }, [agents, selectedDomain]);

  const fleetSummary = useLibraryFleetSummary(filteredAgents);

  useEffect(() => {
    document.title = "Library – AutoGPT Platform";
  }, []);

  function handleTabChange(tabId: string) {
    setActiveTab(tabId);
    setSelectedFolderId(null);
  }

  const handleFavoriteAnimationComplete = useCallback(() => {
    setActiveTab("favorites");
    setSelectedFolderId(null);
  }, []);

  return (
    <FavoriteAnimationProvider
      onAnimationComplete={handleFavoriteAnimationComplete}
    >
      <main className="pt-160 container min-h-screen space-y-4 pb-20 pt-16 sm:px-8 md:px-12">
        <LibraryActionHeader setSearchTerm={setSearchTerm} />
        <DomainSkillPicker
          selectedDomain={selectedDomain}
          onDomainSelect={setSelectedDomain}
        />
        <LibraryAgentList
          searchTerm={searchTerm}
          librarySort={librarySort}
          setLibrarySort={setLibrarySort}
          selectedFolderId={selectedFolderId}
          onFolderSelect={setSelectedFolderId}
          tabs={LIBRARY_TABS}
          activeTab={activeTab}
          onTabChange={handleTabChange}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          selectedDomain={selectedDomain}
          domainFilteredAgents={filteredAgents}
          fleetSummary={isAgentBriefingEnabled ? fleetSummary : undefined}
          briefingAgents={isAgentBriefingEnabled ? agents : undefined}
        />
      </main>
    </FavoriteAnimationProvider>
  );
}
