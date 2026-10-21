import type { Adapter } from "./types";
import { slack } from "./slack";

/**
 * Partner registry. To add a new inbound source (Linear, GitHub, Discord, ...):
 * implement Adapter in ./my-partner.ts and add it here. Nothing else changes —
 * cma.ts dispatches back via `metadata.adapter`.
 */
export const adapters = {
  slack,
} satisfies Record<string, Adapter>;
