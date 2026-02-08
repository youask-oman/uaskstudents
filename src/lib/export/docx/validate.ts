// lib/export/docx/validate.ts
import { z } from "zod";

const blockSchema = z.discriminatedUnion("type", [
    z.object({
        type: z.literal("problem"),
        title: z.string(),
        body: z.string(),
        math: z.array(z.string()).optional(),
        assumptions: z.array(z.string()).optional(),
        originalText: z.string().optional()
    }),
    z.object({ type: z.literal("step"), k: z.number().int().positive(), title: z.string(), body: z.string(), math: z.array(z.string()).optional() }),
    z.object({
        type: z.literal("final"),
        label: z.string(),
        body: z.string(),
        math: z.array(z.string()).optional(),
        values: z.array(z.object({ label: z.string(), value: z.string() })).optional(),
        units: z.string().optional()
    }),
    z.object({ type: z.literal("note"), title: z.string().optional(), body: z.string() }),
    z.object({ type: z.literal("mistakes"), title: z.string(), list: z.array(z.string()) }),
    z.object({
        type: z.literal("plot"),
        title: z.string(),
        xLabel: z.string(),
        yLabel: z.string(),
        points: z.array(z.object({ x: z.number(), y: z.number(), label: z.string().optional() }))
    }),
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
