"use client";

import * as React from "react";

import { Dialog } from "@/components/molecules/Dialog/Dialog";
import { useSupabase } from "@/lib/supabase/hooks/useSupabase";

import { AgentSelectStep } from "./components/AgentSelectStep/AgentSelectStep";
import { AgentInfoStep } from "./components/AgentInfoStep/AgentInfoStep";
import { AgentReviewStep } from "./components/AgentReviewStep";
import {
  PublishAuthPrompt,
  PublishAuthPromptSkeleton,
} from "./components/PublishAuthPrompt";
import { StepStrip } from "./components/StepStrip";
import { Props, usePublishAgentModal } from "./usePublishAgentModal";

export function PublishAgentModal(props: Props) {
  const {
    trigger,
    targetState,
    onStateChange,
    preSelectedAgentId,
    preSelectedAgentVersion,
    showTrigger = true,
  } = props;

  const { isLoggedIn, isUserLoading } = useSupabase();

  const {
    handleClose,
    handleNextFromSelect,
    handleAgentSelect,
    handleGoToDashboard,
    handleGoToBuilder,
    handleSuccessFromInfo,
    handleBack,
    currentState,
    initialData,
    selectedAgentId,
    selectedAgentVersion,
  } = usePublishAgentModal({
    targetState,
    onStateChange,
    preSelectedAgentId,
    preSelectedAgentVersion,
  });

  const isOpen = currentState.isOpen;

  function renderAuthPrompt() {
    if (isUserLoading) {
      return <PublishAuthPromptSkeleton />;
    }

    if (!isLoggedIn) {
      return <PublishAuthPrompt />;
    }

    return null;
  }

  function renderStep() {
    if (isUserLoading || !isLoggedIn) {
      return renderAuthPrompt();
    }

    switch (currentState.step) {
      case "select":
        return (
          <AgentSelectStep
            onSelect={handleAgentSelect}
            onCancel={handleClose}
            onNext={(agentId, agentVersion, agentData) => {
              handleNextFromSelect(agentId, agentVersion, agentData);
            }}
            onOpenBuilder={handleGoToBuilder}
          />
        );
      case "info":
        return (
          <AgentInfoStep
            onBack={handleBack}
            onSuccess={handleSuccessFromInfo}
            selectedAgentId={selectedAgentId}
            selectedAgentVersion={selectedAgentVersion}
            initialData={initialData}
            isMarketplaceUpdate={
              (currentState.submissionData as any)?.isMarketplaceUpdate
            }
          />
        );
      case "review":
        return (
          <AgentReviewStep
            agentName={currentState.submissionData?.name ?? ""}
            subheader={currentState.submissionData?.sub_heading ?? ""}
            description={currentState.submissionData?.description ?? ""}
            thumbnailSrc={
              currentState.submissionData?.image_urls?.[0] ?? undefined
            }
            onClose={handleClose}
            onDone={handleClose}
            onViewProgress={handleGoToDashboard}
            status={currentState.submissionData?.status}
            reviewComments={
              (currentState.submissionData as any)?.review_comments ?? null
            }
          />
        );
      default:
        return null;
    }
  }

  return (
    <Dialog
      onClose={handleClose}
      controlled={{
        isOpen,
        set: async (open) => {
          if (!open) {
            handleClose();
          }
        },
      }}
    >
      {showTrigger && trigger ? (
        <Dialog.Trigger>{trigger}</Dialog.Trigger>
      ) : null}

      <Dialog.Content>
        <div
          data-testid="publish-agent-modal"
          className="flex w-full flex-col px-4 pb-4 pt-4 sm:px-6 sm:pb-6 sm:pt-6"
        >
          <StepStrip currentStep={currentState.step} />
          <div className="flex-1 overflow-y-auto">{renderStep()}</div>
        </div>
      </Dialog.Content>
    </Dialog>
  );
}
