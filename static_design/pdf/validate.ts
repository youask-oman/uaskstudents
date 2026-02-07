// lib/export/docx/validate.ts
import { z } from "zod";

const blockSchema = z.discriminatedUnion("type", [
    z.object({ type: z.literal("problem"), title: z.string(), body: z.string(), math: z.array(z.string()).optional() }),
    z.object({ type: z.literal("step"), k: z.number().int().positive(), title: z.string(), body: z.string(), math: z.array(z.string()).optional() }),
    z.object({ type: z.literal("final"), label: z.string(), body: z.string(), math: z.array(z.string()).optional() }),
    z.object({ type: z.literal("note"), title: z.string().optional(), body: z.string() }),
]);

const payloadSchema = z.object({
    docTitle: z.string().min(1),
    subtitle: z.string().optional(),
    createdAtISO: z.string().min(1),
    pages: z.array(z.object({
        pageTitle: z.string(),
        blocks: z.array(blockSchema),
    })).min(1),
});

export type ExportSolutionPayload = z.infer<typeof payloadSchema>;

export function sanitizePayloadOrThrow(input: unknown): ExportSolutionPayload {
    return payloadSchema.parse(input);
}
