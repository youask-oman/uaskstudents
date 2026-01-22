"use client";

import { useEffect, useState } from "react";

export default function AdminPromptsPage() {
    const [templates, setTemplates] = useState<any[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
    const [versions, setVersions] = useState<any[]>([]);
    const [selectedVersion, setSelectedVersion] = useState<any>(null);
    const [editedContent, setEditedContent] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const [testVariables, setTestVariables] = useState<Record<string, string>>({
        "problem_text": "Find the derivative of f(x) = x^2",
        "subject": "Mathematics",
        "level": "High School"
    });
    const [testResponse, setTestResponse] = useState<string | null>(null);
    const [isTesting, setIsTesting] = useState(false);
    const [activeTab, setActiveTab] = useState<"editor" | "test">("editor");
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    const getAuthHeaders = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) {
            (headers as Record<string, string>)["Content-Type"] = "application/json";
        }
        return headers;
    };

    useEffect(() => {
        const controller = new AbortController();
        const fetchTemplates = async () => {
            try {
                setErrorMessage(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompts`, { headers: getAuthHeaders(), signal: controller.signal });
                if (!res.ok) {
                    throw new Error("Unable to load prompt templates.");
                }
                const data = await res.json();
                setTemplates(data);
                if (data.length > 0) {
                    setSelectedTemplate(data[0]);
                }
            } catch (err) {
                if ((err as Error).name === "AbortError") {
                    return;
                }
                console.error("Failed to fetch templates:", err);
                setErrorMessage("Unable to load prompt templates. Please refresh.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchTemplates();
        return () => controller.abort();
    }, []);

    useEffect(() => {
        if (!selectedTemplate) return;
        const controller = new AbortController();
        const fetchVersions = async () => {
            try {
                setErrorMessage(null);
                const res = await fetch(`${baseUrl}/api/v1/admin/prompts/${selectedTemplate.id}/versions`, { headers: getAuthHeaders(), signal: controller.signal });
                if (!res.ok) {
                    throw new Error("Unable to load prompt versions.");
                }
                const data = await res.json();
                setVersions(data);
                const prod = data.find((v: any) => v.is_production);
                setSelectedVersion(prod || data[0]);
                setEditedContent(prod ? prod.content : (data[0] ? data[0].content : ""));
            } catch (err) {
                if ((err as Error).name === "AbortError") {
                    return;
                }
                console.error("Failed to fetch versions:", err);
                setErrorMessage("Unable to load prompt versions. Please refresh.");
            }
        };
        fetchVersions();
        setTestResponse(null);
        setActiveTab("editor");
        return () => controller.abort();
    }, [selectedTemplate]);

    const handleSaveVersion = async () => {
        if (!selectedTemplate) return;
        setIsSaving(true);
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompts/${selectedTemplate.id}/save`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({ content: editedContent })
            });
            if (res.ok) {
                const vRes = await fetch(`${baseUrl}/api/v1/admin/prompts/${selectedTemplate.id}/versions`, { headers: getAuthHeaders() });
                if (!vRes.ok) {
                    throw new Error("Unable to refresh versions.");
                }
                const vData = await vRes.json();
                setVersions(vData);
                setSelectedVersion(vData[0]);
                alert("Version saved as draft");
            } else {
                throw new Error("Failed to save prompt version.");
            }
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to save prompt version. Please try again.");
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeploy = async () => {
        if (!selectedVersion) return;
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/prompts/versions/${selectedVersion.id}/deploy`, {
                method: "POST",
                headers: getAuthHeaders()
            });
            if (res.ok) {
                const templatesRes = await fetch(`${baseUrl}/api/v1/admin/prompts`, { headers: getAuthHeaders() });
                const versionsRes = await fetch(`${baseUrl}/api/v1/admin/prompts/${selectedTemplate.id}/versions`, { headers: getAuthHeaders() });
                if (!templatesRes.ok || !versionsRes.ok) {
                    throw new Error("Unable to refresh prompt data.");
                }
                setTemplates(await templatesRes.json());
                setVersions(await versionsRes.json());
                alert("Version deployed to production!");
            } else {
                throw new Error("Failed to deploy prompt version.");
            }
        } catch (err) {
            console.error(err);
            setErrorMessage("Failed to deploy prompt version. Please try again.");
        }
    };

    const handleTestPrompt = async () => {
        setIsTesting(true);
        setTestResponse(null);
        try {
            // Mock test for now - in production this would call a backend 'dry-run' endpoint
            await new Promise(r => setTimeout(r, 1500));
            setTestResponse(JSON.stringify({
                "problem": { "goal": "Differentiate x^2", "latex": "f(x) = x^2" },
                "solution": { "steps": [{ "index": 1, "title": "Apply Power Rule", "explanation": "The power rule states...", "math": { "latex_lines": ["f'(x) = 2x"] } }], "final_answer": "2x" }
            }, null, 2));
        } catch (err) {
            setTestResponse("Error testing prompt: " + (err as Error).message);
        } finally {
            setIsTesting(false);
        }
    };

    const getVariablesForSelected = () => {
        if (selectedTemplate?.slug === "tutor-chat") return [
            { name: "{{goal}}", desc: "The identified goal of the problem." },
            { name: "{{latex}}", desc: "The original math problem in LaTeX." }
        ];
        return [
            { name: "{{problem_text}}", desc: "Raw problem string from user." },
            { name: "{{subject}}", desc: "Detected subject (Math, Physics, etc)." },
            { name: "{{level}}", desc: "User's academic level." }
        ];
    };

    if (isLoading) return <div className="p-8 text-slate-400">Loading system explorer...</div>;

    return (
        <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white dark:bg-[#101622]">
            {/* Left Sidebar */}
            <aside className="w-64 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-[#101622] flex flex-col">
                <div className="p-4 flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">System Explorer</h3>
                    <div className="flex gap-2">
                        <span className="material-symbols-outlined text-slate-500 cursor-pointer hover:text-slate-900 dark:text-white transition-colors text-lg">search</span>
                        <span className="material-symbols-outlined text-slate-500 cursor-pointer hover:text-slate-900 dark:text-white transition-colors text-lg">create_new_folder</span>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-4 no-scrollbar">
                    <div>
                        <div className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold text-slate-500 uppercase">
                            <span className="material-symbols-outlined !text-[16px]">expand_more</span>
                            Templates
                        </div>
                        <div className="mt-1 space-y-0.5">
                            {templates.map(t => (
                                <div
                                    key={t.id}
                                    onClick={() => setSelectedTemplate(t)}
                                    className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all group ${selectedTemplate?.id === t.id ? 'bg-admin-primary/20 text-slate-900 dark:text-white' : 'hover:bg-white dark:bg-slate-800 text-slate-400 hover:text-slate-900 dark:text-white'}`}>
                                    <span className={`material-symbols-outlined ${selectedTemplate?.id === t.id ? 'text-admin-primary' : 'text-slate-500'}`}>
                                        {t.slug?.includes("ocr") ? "document_scanner" : t.slug?.includes("vision") ? "visibility" : "function"}
                                    </span>
                                    <span className="text-sm font-medium flex-1 truncate">{t.name}</span>
                                    {t.is_active && <span className="size-2 rounded-full bg-accent-emerald shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Editor */}
            <main className="flex-1 flex flex-col bg-slate-50 dark:bg-[#1a1f29]">
                <div className="px-6 pt-4">
                    {errorMessage && (
                        <div className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs font-bold uppercase tracking-widest text-rose-400">
                            {errorMessage}
                        </div>
                    )}
                    <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                        <span>Admin</span> <span className="text-slate-700">/</span> <span>Prompts</span> <span className="text-slate-700">/</span> <span className="text-slate-300">{selectedTemplate?.name}</span>
                    </div>
                    <div className="flex items-end justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
                        <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl font-black text-slate-900 dark:text-white leading-none tracking-tight">{selectedTemplate?.name}</h1>
                                <span className={`px-2 py-0.5 rounded border text-[10px] font-black uppercase tracking-widest ${selectedVersion?.is_production ? 'bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald' : 'bg-admin-primary/10 border-admin-primary/30 text-admin-primary'}`}>
                                    {selectedVersion?.is_production ? 'Production' : 'Draft'}
                                </span>
                            </div>
                            <p className="text-slate-500 text-[10px] font-bold uppercase tracking-wider">
                                {selectedVersion?.version} — Last edited {new Date(selectedVersion?.created_at).toLocaleString()} by <span className="text-slate-900 dark:text-white">{selectedVersion?.author}</span>
                            </p>
                        </div>
                        <div className="flex gap-2">
                            <select
                                onChange={(e) => {
                                    const v = versions.find(v => v.id === parseInt(e.target.value));
                                    setSelectedVersion(v);
                                    setEditedContent(v.content);
                                    setTestResponse(null);
                                }}
                                value={selectedVersion?.id}
                                className="h-9 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-bold text-slate-300 px-3 focus:ring-1 focus:ring-admin-primary outline-none">
                                {versions.map(v => (
                                    <option key={v.id} value={v.id}>{v.version} {v.is_production ? '(Current)' : ''}</option>
                                ))}
                            </select>
                            <button
                                onClick={handleSaveVersion}
                                disabled={isSaving}
                                className="flex h-9 items-center gap-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 text-xs font-bold text-slate-900 dark:text-white hover:bg-slate-700 transition-all">
                                <span className="material-symbols-outlined !text-lg">save</span>
                                {isSaving ? "Saving..." : "Save Draft"}
                            </button>
                            <button
                                onClick={handleDeploy}
                                className="flex h-9 items-center gap-2 rounded-lg bg-admin-primary px-4 text-xs font-bold text-white hover:bg-admin-primary/90 transition-all shadow-lg shadow-admin-primary/20">
                                <span className="material-symbols-outlined !text-lg">rocket_launch</span>
                                Deploy
                            </button>
                        </div>
                    </div>
                    {/* Tabs */}
                    <div className="flex gap-6 mt-4">
                        <button onClick={() => setActiveTab("editor")} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'editor' ? 'text-admin-primary border-b-2 border-admin-primary' : 'text-slate-500 hover:text-slate-300'}`}>Editor</button>
                        <button onClick={() => setActiveTab("test")} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'test' ? 'text-admin-primary border-b-2 border-admin-primary' : 'text-slate-500 hover:text-slate-300'}`}>Test Execution</button>
                    </div>
                </div>

                <div className="flex-1 flex overflow-hidden border-t border-slate-200 dark:border-slate-800">
                    {activeTab === "editor" ? (
                        <>
                            <div className="w-12 bg-slate-50 dark:bg-white dark:bg-slate-900/30 border-r border-slate-200 dark:border-slate-800 pt-4 text-right pr-3 font-mono text-[10px] leading-6 text-slate-700 select-none">
                                {Array.from({ length: 40 }).map((_, i) => <div key={i}>{i + 1}</div>)}
                            </div>
                            <div className="flex-1 relative">
                                <textarea
                                    value={editedContent}
                                    onChange={(e) => setEditedContent(e.target.value)}
                                    className="w-full h-full bg-transparent border-none focus:ring-0 p-4 font-mono text-sm leading-6 text-slate-300 resize-none no-scrollbar"
                                    placeholder="Enter system prompt instructions here..."
                                />
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col p-6 overflow-y-auto no-scrollbar gap-6">
                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-4">
                                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Test Variables</h3>
                                    <div className="space-y-3 bg-slate-50 dark:bg-white dark:bg-slate-900/50 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
                                        {Object.keys(testVariables).map(key => (
                                            <div key={key} className="flex flex-col gap-1">
                                                <label className="text-[10px] font-bold text-slate-500 uppercase">{key}</label>
                                                <input
                                                    value={testVariables[key]}
                                                    onChange={e => setTestVariables({ ...testVariables, [key]: e.target.value })}
                                                    className="bg-white dark:bg-slate-800 border-none rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-white focus:ring-1 focus:ring-admin-primary"
                                                />
                                            </div>
                                        ))}
                                        <button
                                            onClick={handleTestPrompt}
                                            disabled={isTesting}
                                            className="w-full mt-2 bg-admin-primary text-white py-2 rounded-lg text-xs font-bold hover:bg-admin-primary/90 transition-all flex items-center justify-center gap-2">
                                            {isTesting ? (
                                                <span className="animate-spin size-4 border-2 border-white/20 border-t-white rounded-full"></span>
                                            ) : (
                                                <span className="material-symbols-outlined text-lg">play_arrow</span>
                                            )}
                                            Run Test Simulation
                                        </button>
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Output Preview</h3>
                                    <div className="flex-1 min-h-[300px] bg-white dark:bg-black/40 rounded-xl border border-slate-200 dark:border-slate-800 p-4 font-mono text-xs text-accent-emerald overflow-auto no-scrollbar">
                                        {testResponse ? (
                                            <pre className="whitespace-pre-wrap">{testResponse}</pre>
                                        ) : (
                                            <p className="text-slate-600 italic">Run a test to see JSON output preview here...</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>

            {/* Right Variable Sidebar */}
            <aside className="w-72 flex-shrink-0 border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-[#101622] flex flex-col">
                <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">Global Variables</h3>
                    <span className="material-symbols-outlined text-slate-600 !text-[18px]">info</span>
                </div>
                <div className="p-4 overflow-y-auto flex-1 space-y-6 no-scrollbar">
                    <div>
                        <p className="text-[10px] font-black text-slate-600 uppercase mb-3 tracking-[0.15em]">Injection Context</p>
                        <div className="space-y-2">
                            {getVariablesForSelected().map(v => (
                                <div key={v.name}
                                    onClick={() => setEditedContent(prev => prev + " " + v.name)}
                                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-white dark:bg-slate-900/40 hover:border-admin-primary/50 cursor-pointer group transition-all">
                                    <div className="flex items-center justify-between mb-1">
                                        <code className="text-admin-primary text-[11px] font-black">{v.name}</code>
                                        <span className="material-symbols-outlined !text-[14px] text-slate-700 group-hover:text-admin-primary">add_circle</span>
                                    </div>
                                    <p className="text-[10px] text-slate-500 leading-normal font-medium">{v.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="p-4 rounded-xl bg-admin-primary/5 border border-admin-primary/10 mt-auto">
                        <p className="text-[10px] font-black text-slate-900 dark:text-white mb-2 flex items-center gap-2 uppercase tracking-widest">
                            <span className="material-symbols-outlined !text-sm text-admin-primary">lightbulb</span>
                            Developer Tip
                        </p>
                        <p className="text-[10px] text-slate-500 leading-relaxed font-medium">
                            Click on a variable to insert it at the current cursor position. Ensure your template handles missing data gracefully.
                        </p>
                    </div>
                </div>
            </aside>
        </div>
    );
}
