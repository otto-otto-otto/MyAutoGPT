-- Fix: Rewrite all remaining foreign model values to DeepSeek V3
-- The previous migration (20260512120000) incorrectly mapped legacy models
-- to newer foreign models that no longer exist in the LlmModel enum.
-- This fix rewrites them to deepseek-chat to match LEGACY_MODEL_MAPPINGS in llm.py.
--
-- Catch-all: any value NOT in the current LlmModel enum → deepseek-chat

-- Current valid model values from LlmModel enum:
-- deepseek-chat, deepseek-reasoner
-- ernie-4.0-turbo-128k, ernie-speed-pro-128k, ernie-lite-pro-128k
-- qwen-max, qwen-plus, qwen-turbo
-- llama3.3, llama3.2, llama3, llama3.1:405b, dolphin-mistral:latest
-- z-ai/glm-4.6, z-ai/glm-4.6v, z-ai/glm-4.7, z-ai/glm-4.7-flash, z-ai/glm-5, z-ai/glm-5-turbo, z-ai/glm-5v-turbo
-- qwen/qwen3-235b-a22b-thinking-2507, qwen/qwen3-coder

-- Fix AgentNode.constantInput — any model value not in current enum → deepseek-chat
UPDATE "AgentNode"
SET    "constantInput" = JSONB_SET(
         "constantInput"::jsonb,
         '{model}',
         '"deepseek-chat"'::jsonb
       )
WHERE  "constantInput"::jsonb->>'model' IS NOT NULL
  AND  "constantInput"::jsonb->>'model' NOT IN (
         'deepseek-chat', 'deepseek-reasoner',
         'ernie-4.0-turbo-128k', 'ernie-speed-pro-128k', 'ernie-lite-pro-128k',
         'qwen-max', 'qwen-plus', 'qwen-turbo',
         'llama3.3', 'llama3.2', 'llama3', 'llama3.1:405b', 'dolphin-mistral:latest',
         'z-ai/glm-4.6', 'z-ai/glm-4.6v', 'z-ai/glm-4.7', 'z-ai/glm-4.7-flash',
         'z-ai/glm-5', 'z-ai/glm-5-turbo', 'z-ai/glm-5v-turbo',
         'qwen/qwen3-235b-a22b-thinking-2507', 'qwen/qwen3-coder'
       );

-- Fix AgentNodeExecutionInputOutput.data for preset overrides
UPDATE "AgentNodeExecutionInputOutput"
SET    "data" = JSONB_SET(
         "data"::jsonb,
         '{model}',
         '"deepseek-chat"'::jsonb
       )
WHERE  "agentPresetId" IS NOT NULL
  AND  "data"::jsonb->>'model' IS NOT NULL
  AND  "data"::jsonb->>'model' NOT IN (
         'deepseek-chat', 'deepseek-reasoner',
         'ernie-4.0-turbo-128k', 'ernie-speed-pro-128k', 'ernie-lite-pro-128k',
         'qwen-max', 'qwen-plus', 'qwen-turbo',
         'llama3.3', 'llama3.2', 'llama3', 'llama3.1:405b', 'dolphin-mistral:latest',
         'z-ai/glm-4.6', 'z-ai/glm-4.6v', 'z-ai/glm-4.7', 'z-ai/glm-4.7-flash',
         'z-ai/glm-5', 'z-ai/glm-5-turbo', 'z-ai/glm-5v-turbo',
         'qwen/qwen3-235b-a22b-thinking-2507', 'qwen/qwen3-coder'
       );
