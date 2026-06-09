import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }

  // During `next build`, Next.js evaluates instrumentation.ts in an edge
  // runtime context. On Node.js 22.x + Next.js 15.5 this can trigger a V8
  // "unreachable code" fatal engine crash (not catchable as a JS error).
  // Skip edge Sentry init during the build phase – it loads at runtime.
  if (
    process.env.NEXT_RUNTIME === "edge" &&
    process.env.NEXT_PHASE !== "phase-production-build"
  ) {
    await import("../sentry.edge.config");
  }
}

export const onRequestError = Sentry.captureRequestError;
