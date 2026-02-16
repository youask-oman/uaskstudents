import { z } from "zod";

export const CreditsBalanceSchema = z.object({
  user_id: z.union([z.string(), z.number()]),
  available_credits: z.number(),
  reserved_credits: z.number(),
  expiring_soon_credits: z.number().optional(),
  lots_summary: z
    .object({
      total_lots: z.number().optional(),
      active_lots: z.number().optional(),
    })
    .optional(),
});

export const CreditsHoldItemSchema = z.object({
  hold_id: z.string(),
  status: z.string(),
  reserved: z.number(),
  settled: z.number(),
  released: z.number(),
  created_at: z.string(),
  expires_at: z.string().nullable().optional(),
  tier: z.string().optional(),
  action: z.string().optional(),
  request_id: z.string().nullable().optional(),
  attempt_id: z.string().nullable().optional(),
});

export const CreditsHoldsPageSchema = z.object({
  items: z.array(CreditsHoldItemSchema),
  next_cursor: z.string().nullable().optional(),
  limit: z.number().optional(),
});

export const CreditsLedgerItemSchema = z.object({
  ledger_id: z.string().optional(),
  tier: z.string(),
  action: z.string(),
  question_index: z.number().nullable().optional(),
  total_cost: z.number(),
  outcome: z.string(),
  created_at: z.string(),
  request_id: z.string().nullable().optional(),
  attempt_id: z.string().nullable().optional(),
});

export const CreditsLedgerPageSchema = z.object({
  items: z.array(CreditsLedgerItemSchema),
  next_cursor: z.string().nullable().optional(),
  limit: z.number().optional(),
});

export const CreditsLotsPageSchema = z.object({
  items: z.array(
    z.object({
      lot_id: z.string(),
      source: z.string().optional(),
      credits_total: z.number(),
      credits_remaining: z.number(),
      expires_at: z.string().nullable().optional(),
      created_at: z.string(),
    })
  ),
  next_cursor: z.string().nullable().optional(),
  limit: z.number().optional(),
});

export const CreditsPacksSchema = z.object({
  items: z.array(
    z.object({
      pack_code: z.string(),
      credits: z.number(),
      label: z.string().nullable().optional(),
      active: z.boolean(),
      sort_order: z.number().optional(),
      display_name: z.string().nullable().optional(),
      stripe_mapping: z
        .object({
          stripe_price_id: z.string().nullable().optional(),
          mapped: z.boolean().optional(),
        })
        .optional(),
    })
  ),
});

export const SolveBatchItemSchema = z.object({
  question_id: z.string().optional(),
  question_index: z.number().optional(),
  refusal: z
    .object({
      is_refusal: z.boolean(),
      reason: z.string().nullable().optional(),
    })
    .optional(),
  final_answer: z
    .union([
      z.string(),
      z.object({
        answer_text: z.string().optional(),
        answer_latex: z.string().nullable().optional(),
        answer: z.string().optional(),
        latex: z.string().optional(),
        text: z.string().optional(),
        value: z.union([z.string(), z.number(), z.boolean(), z.null()]).optional(),
      }).passthrough(),
      z.null(),
    ])
    .optional(),
});

export const SolveBatchResponseSchema = z.object({
  request_id: z.string().optional(),
  attempt_id: z.string().optional(),
  session_id: z.union([z.number(), z.string()]).optional(),
  items: z.array(SolveBatchItemSchema),
});

export type SolveBatchResponse = z.infer<typeof SolveBatchResponseSchema>;
