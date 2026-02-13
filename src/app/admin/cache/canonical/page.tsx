"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL, parseApiError } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

type CanonicalProblem = {
  id: number;
  normalized_problem_hash: string;
  normalized_text: string;
  intent: string;
  canonical_math_object: string;
  assumptions_hash?: string | null;
  prompt_version?: string | null;
  solver_version?: string | null;
  schema_version?: string | null;
  subject?: string | null;
  language: string;
  seen_count: number;
  created_at: string;
  last_seen_at: string;
};

type CanonicalSolution = {
  id: number;
  problem_id: number;
  solution_json: Record<string, unknown>;
  verification_status: string;
  verification_report?: Record<string, unknown> | null;
  prompt_version?: string | null;
  model_id?: string | null;
  served_count: number;
  created_at: string;
  last_served_at: string;
};

export default function AdminCanonicalCachePage() {
  const { pushToast } = useToast();
  const [tab, setTab] = useState<"problems" | "solutions">("problems");
  const [problems, setProblems] = useState<CanonicalProblem[]>([]);
  const [solutions, setSolutions] = useState<CanonicalSolution[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [reason, setReason] = useState("");
  const [showProblemCreate, setShowProblemCreate] = useState(false);
  const [showSolutionCreate, setShowSolutionCreate] = useState(false);
  const [editingProblem, setEditingProblem] = useState<CanonicalProblem | null>(null);
  const [editingSolution, setEditingSolution] = useState<CanonicalSolution | null>(null);
  const [newProblem, setNewProblem] = useState({
    normalized_problem_hash: "",
    normalized_text: "",
    intent: "unknown",
    canonical_math_object: "",
    language: "en",
  });
  const [newSolution, setNewSolution] = useState({
    problem_id: 0,
    verification_status: "pending",
    solution_json: "{}",
  });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const baseUrl = API_BASE_URL;
  const fallbackUrl = process.env.NEXT_PUBLIC_API_FALLBACK_URL || API_BASE_URL || "http://localhost:9000";

  const getHeaders = (contentType = false): HeadersInit => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    return {
      ...(contentType ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchAdmin = async (path: string, init?: RequestInit) => {
    const run = async (urlBase: string) =>
      fetch(`${urlBase}${path}`, {
        ...init,
        headers: {
          ...getHeaders(Boolean(init?.body)),
          ...(init?.headers || {}),
        },
      });
    try {
      return await run(baseUrl);
    } catch {
      if (baseUrl !== fallbackUrl) {
        return run(fallbackUrl);
      }
      throw new Error("Network error");
    }
  };

  const filteredProblems = useMemo(() => {
    if (!q.trim()) return problems;
    const needle = q.toLowerCase();
    return problems.filter((x) => JSON.stringify(x).toLowerCase().includes(needle));
  }, [problems, q]);

  const filteredSolutions = useMemo(() => {
    if (!q.trim()) return solutions;
    const needle = q.toLowerCase();
    return solutions.filter((x) => JSON.stringify(x).toLowerCase().includes(needle));
  }, [solutions, q]);

  const refreshProblems = async () => {
    setLoading(true);
    try {
      const res = await fetchAdmin(`/api/v1/admin/cache/canonical/problems?limit=200`);
      if (!res.ok) throw new Error((await parseApiError(res)).message);
      const data = await res.json();
      setProblems(Array.isArray(data.items) ? data.items : []);
      setErrorMessage(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load problems";
      setErrorMessage(message);
      pushToast({ type: "error", title: "Failed", message });
    } finally {
      setLoading(false);
    }
  };

  const refreshSolutions = async () => {
    setLoading(true);
    try {
      const res = await fetchAdmin(`/api/v1/admin/cache/canonical/solutions?limit=200`);
      if (!res.ok) throw new Error((await parseApiError(res)).message);
      const data = await res.json();
      setSolutions(Array.isArray(data.items) ? data.items : []);
      setErrorMessage(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load solutions";
      setErrorMessage(message);
      pushToast({ type: "error", title: "Failed", message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshProblems();
    void refreshSolutions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const deleteProblem = async (id: number) => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/problems/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Delete failed", message: (await parseApiError(res)).message });
    await refreshProblems();
    await refreshSolutions();
  };

  const createProblem = async () => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/problems`, {
      method: "POST",
      body: JSON.stringify({ ...newProblem, reason, seen_count: 1 }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Create failed", message: (await parseApiError(res)).message });
    setShowProblemCreate(false);
    setNewProblem({ normalized_problem_hash: "", normalized_text: "", intent: "unknown", canonical_math_object: "", language: "en" });
    await refreshProblems();
  };

  const updateProblem = async () => {
    if (!editingProblem) return;
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/problems/${editingProblem.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        normalized_text: editingProblem.normalized_text,
        intent: editingProblem.intent,
        canonical_math_object: editingProblem.canonical_math_object,
        language: editingProblem.language,
        seen_count: editingProblem.seen_count,
        reason,
      }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Update failed", message: (await parseApiError(res)).message });
    setEditingProblem(null);
    await refreshProblems();
  };

  const deleteSolution = async (id: number) => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/solutions/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Delete failed", message: (await parseApiError(res)).message });
    await refreshSolutions();
  };

  const createSolution = async () => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(newSolution.solution_json || "{}");
    } catch {
      return pushToast({ type: "error", title: "Invalid JSON", message: "solution_json must be valid JSON." });
    }
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/solutions`, {
      method: "POST",
      body: JSON.stringify({
        problem_id: newSolution.problem_id,
        solution_json: parsed,
        verification_status: newSolution.verification_status,
        reason,
      }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Create failed", message: (await parseApiError(res)).message });
    setShowSolutionCreate(false);
    setNewSolution({ problem_id: 0, verification_status: "pending", solution_json: "{}" });
    await refreshSolutions();
  };

  const updateSolution = async () => {
    if (!editingSolution) return;
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/solutions/${editingSolution.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        problem_id: editingSolution.problem_id,
        verification_status: editingSolution.verification_status,
        served_count: editingSolution.served_count,
        solution_json: editingSolution.solution_json,
        reason,
      }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Update failed", message: (await parseApiError(res)).message });
    setEditingSolution(null);
    await refreshSolutions();
  };

  const bumpProblemSeen = async (item: CanonicalProblem) => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/problems/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ seen_count: item.seen_count + 1, reason }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Update failed", message: (await parseApiError(res)).message });
    await refreshProblems();
  };

  const bumpSolutionServed = async (item: CanonicalSolution) => {
    if (!reason.trim()) return pushToast({ type: "error", title: "Reason required", message: "Enter reason first." });
    const res = await fetchAdmin(`/api/v1/admin/cache/canonical/solutions/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ served_count: item.served_count + 1, reason }),
    });
    if (!res.ok) return pushToast({ type: "error", title: "Update failed", message: (await parseApiError(res)).message });
    await refreshSolutions();
  };

  return (
    <div className="p-8 max-w-[1500px] mx-auto w-full flex flex-col gap-5">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Canonical Cache</h2>
      <p className="text-sm text-slate-500">Full control over `canonicalproblem` and `canonicalsolution`.</p>
      {errorMessage && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {errorMessage}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button onClick={() => setTab("problems")} className={`px-4 py-2 rounded-lg text-sm font-semibold ${tab === "problems" ? "bg-admin-primary text-white" : "bg-slate-200"}`}>Problems</button>
        <button onClick={() => setTab("solutions")} className={`px-4 py-2 rounded-lg text-sm font-semibold ${tab === "solutions" ? "bg-admin-primary text-white" : "bg-slate-200"}`}>Solutions</button>
        <input value={q} onChange={(e) => setQ(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm min-w-[260px]" placeholder="Search..." />
        <input value={reason} onChange={(e) => setReason(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm min-w-[320px]" placeholder="Audit reason (required for mutate)" />
        <button onClick={() => void (tab === "problems" ? refreshProblems() : refreshSolutions())} className="px-4 py-2 rounded-lg bg-slate-700 text-white text-sm">Refresh</button>
        <button onClick={() => setShowProblemCreate((v) => (tab === "problems" ? !v : v))} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">New Problem</button>
        <button onClick={() => setShowSolutionCreate((v) => (tab === "solutions" ? !v : v))} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">New Solution</button>
      </div>

      {tab === "problems" && showProblemCreate && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input value={newProblem.normalized_problem_hash} onChange={(e) => setNewProblem({ ...newProblem, normalized_problem_hash: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="normalized_problem_hash" />
          <input value={newProblem.intent} onChange={(e) => setNewProblem({ ...newProblem, intent: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="intent" />
          <textarea value={newProblem.normalized_text} onChange={(e) => setNewProblem({ ...newProblem, normalized_text: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" placeholder="normalized_text" rows={3} />
          <textarea value={newProblem.canonical_math_object} onChange={(e) => setNewProblem({ ...newProblem, canonical_math_object: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" placeholder="canonical_math_object" rows={2} />
          <button onClick={() => void createProblem()} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">Create Problem</button>
        </div>
      )}

      {tab === "solutions" && showSolutionCreate && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input type="number" value={newSolution.problem_id || ""} onChange={(e) => setNewSolution({ ...newSolution, problem_id: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" placeholder="problem_id" />
          <input value={newSolution.verification_status} onChange={(e) => setNewSolution({ ...newSolution, verification_status: e.target.value })} className="px-3 py-2 rounded-lg border" placeholder="verification_status" />
          <textarea value={newSolution.solution_json} onChange={(e) => setNewSolution({ ...newSolution, solution_json: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" placeholder="solution_json" rows={6} />
          <button onClick={() => void createSolution()} className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm">Create Solution</button>
        </div>
      )}

      {tab === "problems" && (
        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-auto max-h-[720px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Hash</th>
                <th className="px-3 py-2 text-left">Intent</th>
                <th className="px-3 py-2 text-left">Seen</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProblems.map((p) => (
                <tr key={p.id} className="border-t border-slate-200 dark:border-slate-800">
                  <td className="px-3 py-2">{p.id}</td>
                  <td className="px-3 py-2 font-mono text-xs">{p.normalized_problem_hash}</td>
                  <td className="px-3 py-2">{p.intent}</td>
                  <td className="px-3 py-2">{p.seen_count}</td>
                  <td className="px-3 py-2 flex gap-2">
                    <button onClick={() => void bumpProblemSeen(p)} className="px-2 py-1 rounded bg-blue-600 text-white text-xs">+Seen</button>
                    <button onClick={() => setEditingProblem({ ...p })} className="px-2 py-1 rounded bg-slate-700 text-white text-xs">Edit</button>
                    <button onClick={() => void deleteProblem(p.id)} className="px-2 py-1 rounded bg-rose-600 text-white text-xs">Delete</button>
                  </td>
                </tr>
              ))}
              {!loading && filteredProblems.length === 0 && (
                <tr><td className="px-3 py-4 text-slate-500" colSpan={5}>No canonical problems.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "solutions" && (
        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-auto max-h-[720px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Problem ID</th>
                <th className="px-3 py-2 text-left">Verification</th>
                <th className="px-3 py-2 text-left">Served</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSolutions.map((s) => (
                <tr key={s.id} className="border-t border-slate-200 dark:border-slate-800">
                  <td className="px-3 py-2">{s.id}</td>
                  <td className="px-3 py-2">{s.problem_id}</td>
                  <td className="px-3 py-2">{s.verification_status}</td>
                  <td className="px-3 py-2">{s.served_count}</td>
                  <td className="px-3 py-2 flex gap-2">
                    <button onClick={() => void bumpSolutionServed(s)} className="px-2 py-1 rounded bg-blue-600 text-white text-xs">+Served</button>
                    <button onClick={() => setEditingSolution({ ...s })} className="px-2 py-1 rounded bg-slate-700 text-white text-xs">Edit</button>
                    <button onClick={() => void deleteSolution(s.id)} className="px-2 py-1 rounded bg-rose-600 text-white text-xs">Delete</button>
                  </td>
                </tr>
              ))}
              {!loading && filteredSolutions.length === 0 && (
                <tr><td className="px-3 py-4 text-slate-500" colSpan={5}>No canonical solutions.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editingProblem && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input value={editingProblem.intent} onChange={(e) => setEditingProblem({ ...editingProblem, intent: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <input value={editingProblem.language} onChange={(e) => setEditingProblem({ ...editingProblem, language: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <textarea value={editingProblem.normalized_text} onChange={(e) => setEditingProblem({ ...editingProblem, normalized_text: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" rows={3} />
          <textarea value={editingProblem.canonical_math_object} onChange={(e) => setEditingProblem({ ...editingProblem, canonical_math_object: e.target.value })} className="px-3 py-2 rounded-lg border md:col-span-2" rows={2} />
          <input type="number" value={editingProblem.seen_count} onChange={(e) => setEditingProblem({ ...editingProblem, seen_count: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" />
          <div className="flex gap-2">
            <button onClick={() => void updateProblem()} className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm">Save</button>
            <button onClick={() => setEditingProblem(null)} className="px-4 py-2 rounded-lg bg-slate-500 text-white text-sm">Close</button>
          </div>
        </div>
      )}

      {editingSolution && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
          <input type="number" value={editingSolution.problem_id} onChange={(e) => setEditingSolution({ ...editingSolution, problem_id: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" />
          <input value={editingSolution.verification_status} onChange={(e) => setEditingSolution({ ...editingSolution, verification_status: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <input type="number" value={editingSolution.served_count} onChange={(e) => setEditingSolution({ ...editingSolution, served_count: Number(e.target.value) || 0 })} className="px-3 py-2 rounded-lg border" />
          <input value={editingSolution.model_id || ""} onChange={(e) => setEditingSolution({ ...editingSolution, model_id: e.target.value })} className="px-3 py-2 rounded-lg border" />
          <textarea value={JSON.stringify(editingSolution.solution_json || {}, null, 2)} onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              setEditingSolution({ ...editingSolution, solution_json: parsed });
            } catch {
              // keep old value until valid JSON
            }
          }} className="px-3 py-2 rounded-lg border md:col-span-2 font-mono text-xs" rows={6} />
          <div className="flex gap-2">
            <button onClick={() => void updateSolution()} className="px-4 py-2 rounded-lg bg-admin-primary text-white text-sm">Save</button>
            <button onClick={() => setEditingSolution(null)} className="px-4 py-2 rounded-lg bg-slate-500 text-white text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
