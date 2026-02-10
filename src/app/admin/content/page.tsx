"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

const PAGE_TITLE = "Content Library";

type Concept = {
    id: number;
    normalized_problem_hash: string;
    subject?: string | null;
    intent: string;
    normalized_text: string;
    created_at: string;
    last_seen_at: string;
    seen_count: number;
};

type ConceptResponse = {
    items: Concept[];
    total: number;
    limit: number;
    offset: number;
    subjects: string[];
};

export default function AdminContentManagementPage() {
    const { pushToast } = useToast();
    const [concepts, setConcepts] = useState<Concept[]>([]);
    const [subjects, setSubjects] = useState<string[]>([]);
    const [search, setSearch] = useState("");
    const [subjectFilter, setSubjectFilter] = useState("");
    const [limit, setLimit] = useState(25);
    const [offset, setOffset] = useState(0);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);

    const page = Math.floor(offset / limit) + 1;
    const totalPages = Math.max(1, Math.ceil(total / limit));

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem("token");
            const params = new URLSearchParams();
            if (search.trim()) params.set("search", search.trim());
            if (subjectFilter) params.set("subject", subjectFilter);
            params.set("limit", limit.toString());
            params.set("offset", offset.toString());

            const res = await fetch(`${API_BASE_URL}/api/admin/content/concepts?${params.toString()}`,
                {
                    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                }
            );
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Failed to load content",
                    message: err.message,
                    requestId: err.requestId,
                });
                setLoading(false);
                return;
            }
            const data = (await res.json()) as ConceptResponse;
            setConcepts(data.items || []);
            setTotal(data.total || 0);
            setSubjects(data.subjects || []);
        } catch (error) {
            pushToast({
                type: "error",
                title: "Failed to load content",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        } finally {
            setLoading(false);
        }
    }, [limit, offset, search, subjectFilter, pushToast]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useEffect(() => {
        setOffset(0);
    }, [search, subjectFilter, limit]);

    const previewText = useMemo(() => {
        return concepts.map((concept) => {
            const text = concept.normalized_text || "";
            if (text.length <= 140) return text;
            return `${text.slice(0, 140)}...`;
        });
    }, [concepts]);

    return (
        <div className="p-8 max-w-[1400px] mx-auto w-full flex flex-col gap-6">
            <header className="flex flex-col gap-2">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{PAGE_TITLE}</h2>
                <p className="text-sm text-slate-500">
                    Canonical content inventory sourced from production solves. Read-only view for audit and QA.
                </p>
            </header>

            <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-700 px-4 py-3 text-xs font-semibold uppercase tracking-widest">
                Read-only: content is managed by ingestion pipelines and solver QA workflows.
            </div>

            <div className="flex flex-wrap gap-3 items-center">
                <div className="flex-1 min-w-[260px]">
                    <input
                        className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-500"
                        placeholder="Search canonical hash or normalized text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <select
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-white"
                    value={subjectFilter}
                    onChange={(e) => setSubjectFilter(e.target.value)}
                >
                    <option value="">All subjects</option>
                    {subjects.map((subject) => (
                        <option key={subject} value={subject}>
                            {subject}
                        </option>
                    ))}
                </select>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>Rows</span>
                    <input
                        className="w-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-900 dark:text-white"
                        type="number"
                        min={5}
                        max={200}
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                    />
                </div>
            </div>

            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full text-left">
                        <thead className="bg-slate-50 dark:bg-slate-900/50">
                            <tr>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Hash</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Subject</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Intent</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Seen</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Last Seen</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Preview</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {loading ? (
                                <tr>
                                    <td colSpan={6} className="px-4 py-6 text-center text-sm text-slate-500">
                                        Loading content...
                                    </td>
                                </tr>
                            ) : concepts.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-4 py-6 text-center text-sm text-slate-500">
                                        No canonical content found.
                                    </td>
                                </tr>
                            ) : (
                                concepts.map((concept, idx) => (
                                    <tr key={concept.id} className="hover:bg-slate-100 dark:hover:bg-slate-800/40 transition-colors">
                                        <td className="px-4 py-3 text-[11px] font-mono text-slate-600 dark:text-slate-300">
                                            {concept.normalized_problem_hash}
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300">
                                            {concept.subject || "Unclassified"}
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300">
                                            {concept.intent}
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300">
                                            {concept.seen_count}
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300">
                                            {new Date(concept.last_seen_at).toLocaleString()}
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-slate-600 dark:text-slate-300">
                                            {previewText[idx]}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            <div className="flex items-center justify-between text-xs text-slate-500">
                <span>
                    Page {page} of {totalPages} - {total.toLocaleString()} records
                </span>
                <div className="flex gap-2">
                    <button
                        className="px-3 py-1 rounded border border-slate-200 dark:border-slate-800 disabled:opacity-50"
                        onClick={() => setOffset(Math.max(0, offset - limit))}
                        disabled={page <= 1}
                    >
                        Prev
                    </button>
                    <button
                        className="px-3 py-1 rounded border border-slate-200 dark:border-slate-800 disabled:opacity-50"
                        onClick={() => setOffset(Math.min(offset + limit, (totalPages - 1) * limit))}
                        disabled={page >= totalPages}
                    >
                        Next
                    </button>
                </div>
            </div>
        </div>
    );
}
