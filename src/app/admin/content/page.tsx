"use client";

import MathRenderer from "@/components/math/MathRendererSwitch";

export default function AdminContentManagementPage() {
    return (
        <>
            <header className="bg-white/80 dark:bg-white dark:bg-admin-bg-dark/80 backdrop-blur-md border-b border-slate-200 dark:border-border-dark pt-8 px-10">
                <div className="flex justify-between items-center mb-8">
                    <div className="flex flex-col gap-1">
                        <h2 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">Manage Collections</h2>
                        <p className="text-sm text-slate-500 font-medium">Vector database administration and metadata control</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-3 px-4 py-2 rounded-full bg-neon-green/10 border border-neon-green/20 text-neon-green text-[10px] font-bold uppercase tracking-widest">
                            <span className="size-2 rounded-full bg-neon-green animate-pulse"></span>
                            Qdrant Active: Node 01
                        </div>
                    </div>
                </div>
                <div className="flex gap-10 overflow-x-auto no-scrollbar">
                    <a className="flex flex-col items-center justify-center border-b-2 border-admin-primary text-admin-primary pb-4 px-1" href="#">
                        <p className="text-xs font-bold uppercase tracking-widest whitespace-nowrap">Concept Cards</p>
                    </a>
                    <a className="flex flex-col items-center justify-center border-b-2 border-transparent text-slate-500 hover:text-slate-300 pb-4 px-1 transition-colors" href="#">
                        <p className="text-xs font-bold uppercase tracking-widest whitespace-nowrap">Worked Examples</p>
                    </a>
                    <a className="flex flex-col items-center justify-center border-b-2 border-transparent text-slate-500 hover:text-slate-300 pb-4 px-1 transition-colors" href="#">
                        <p className="text-xs font-bold uppercase tracking-widest whitespace-nowrap">Hint Snippets</p>
                    </a>
                    <a className="flex flex-col items-center justify-center border-b-2 border-transparent text-slate-500 hover:text-slate-300 pb-4 px-1 transition-colors" href="#">
                        <p className="text-xs font-bold uppercase tracking-widest whitespace-nowrap">Import/Export</p>
                    </a>
                </div>
            </header>
            <div className="px-10 py-6">
                <div className="flex flex-col lg:flex-row gap-4 justify-between items-start lg:items-center bg-surface-dark p-2 rounded-xl border border-slate-200 dark:border-border-dark">
                    <div className="flex flex-1 gap-3 items-center w-full">
                        <div className="flex-1 max-w-lg pl-2">
                            <label className="flex flex-col h-10 w-full">
                                <div className="flex w-full flex-1 items-stretch rounded-lg bg-white/50 dark:bg-white dark:bg-admin-bg-dark/50 border border-slate-200 dark:border-border-dark focus-within:border-admin-primary transition-all">
                                    <div className="text-slate-500 flex items-center justify-center pl-3">
                                        <span className="material-symbols-outlined text-[20px]">search</span>
                                    </div>
                                    <input className="form-input flex w-full border-none bg-transparent focus:ring-0 text-sm font-normal text-slate-200 placeholder:text-slate-600" placeholder="Search concept ID, titles, or subjects..." />
                                </div>
                            </label>
                        </div>
                        <div className="flex gap-2">
                            <button className="flex h-10 shrink-0 items-center justify-center gap-x-2 rounded-lg bg-white dark:bg-admin-bg-dark border border-slate-200 dark:border-border-dark px-4 hover:border-admin-primary transition-all text-slate-300">
                                <p className="text-xs font-semibold">Subject: All</p>
                                <span className="material-symbols-outlined text-[16px]">expand_more</span>
                            </button>
                            <button className="flex h-10 shrink-0 items-center justify-center gap-x-2 rounded-lg bg-white dark:bg-admin-bg-dark border border-slate-200 dark:border-border-dark px-4 hover:border-admin-primary transition-all text-slate-300">
                                <p className="text-xs font-semibold">Level: All</p>
                                <span className="material-symbols-outlined text-[16px]">expand_more</span>
                            </button>
                        </div>
                    </div>
                    <button className="flex h-10 min-w-[150px] items-center justify-center gap-2 rounded-lg bg-admin-primary px-6 text-white text-xs font-bold uppercase tracking-widest hover:bg-primary-hover transition-all shadow-lg shadow-admin-primary/20">
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        <span>Add Concept</span>
                    </button>
                </div>
            </div>
            <div className="flex-1 overflow-auto px-10 pb-10 no-scrollbar">
                <div className="bg-surface-dark rounded-xl border border-slate-200 dark:border-border-dark overflow-hidden shadow-2xl">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-white/40 dark:bg-white dark:bg-admin-bg-dark/40 border-b border-slate-200 dark:border-border-dark">
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Title / Entity</th>
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Metadata (LaTeX)</th>
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Subject</th>
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Status</th>
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Last Patch</th>
                                <th className="px-8 py-5 text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border-dark">
                            <tr className="hover:bg-admin-primary/5 transition-colors group">
                                <td className="px-8 py-5">
                                    <div className="flex flex-col gap-0.5">
                                        <span className="text-sm font-semibold text-slate-200 group-hover:text-slate-900 dark:text-white transition-colors">Pythagorean Theorem</span>
                                        <span className="text-[10px] font-mono text-slate-500 bg-white dark:bg-admin-bg-dark w-fit px-1.5 py-0.5 rounded border border-slate-200 dark:border-border-dark">CC-MATH-9012</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="latex-white text-sm font-medium">
                                        <MathRenderer content={"a^2 + b^2 = c^2"} mode="inline" />
                                    </span>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="text-xs font-medium text-slate-400">Mathematics</span>
                                </td>
                                <td className="px-8 py-5">
                                    <div className="flex items-center gap-2.5">
                                        <span className="size-2 rounded-full bg-neon-green shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
                                        <span className="text-xs font-bold text-neon-green uppercase tracking-wider">Indexed</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5 text-xs text-slate-500 font-medium">2.4h ago</td>
                                <td className="px-8 py-5 text-right">
                                    <div className="flex justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                                        <button className="p-2 text-slate-400 hover:text-admin-primary transition-colors hover:bg-admin-primary/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">edit</span></button>
                                        <button className="p-2 text-slate-400 hover:text-red-400 transition-colors hover:bg-red-500/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">delete</span></button>
                                    </div>
                                </td>
                            </tr>
                            <tr className="hover:bg-admin-primary/5 transition-colors group">
                                <td className="px-8 py-5">
                                    <div className="flex flex-col gap-0.5">
                                        <span className="text-sm font-semibold text-slate-200 group-hover:text-slate-900 dark:text-white transition-colors">Maxwell Equations</span>
                                        <span className="text-[10px] font-mono text-slate-500 bg-white dark:bg-admin-bg-dark w-fit px-1.5 py-0.5 rounded border border-slate-200 dark:border-border-dark">CC-PHYS-3312</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="latex-white text-sm font-medium">
                                        <MathRenderer content={"\\nabla \\cdot E = \\rho / \\varepsilon_0"} mode="inline" />
                                    </span>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="text-xs font-medium text-slate-400">Physics</span>
                                </td>
                                <td className="px-8 py-5">
                                    <div className="flex items-center gap-2.5">
                                        <span className="size-2 rounded-full bg-neon-amber shadow-[0_0_8px_rgba(245,158,11,0.6)]"></span>
                                        <span className="text-xs font-bold text-neon-amber uppercase tracking-wider">Pending</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5 text-xs text-slate-500 font-medium">5.1h ago</td>
                                <td className="px-8 py-5 text-right">
                                    <div className="flex justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                                        <button className="p-2 text-slate-400 hover:text-admin-primary transition-colors hover:bg-admin-primary/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">edit</span></button>
                                        <button className="p-2 text-slate-400 hover:text-red-400 transition-colors hover:bg-red-500/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">delete</span></button>
                                    </div>
                                </td>
                            </tr>
                            <tr className="hover:bg-admin-primary/5 transition-colors group">
                                <td className="px-8 py-5">
                                    <div className="flex flex-col gap-0.5">
                                        <span className="text-sm font-semibold text-slate-200 group-hover:text-slate-900 dark:text-white transition-colors">Quantum State</span>
                                        <span className="text-[10px] font-mono text-slate-500 bg-white dark:bg-admin-bg-dark w-fit px-1.5 py-0.5 rounded border border-slate-200 dark:border-border-dark">CC-PHYS-1002</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="latex-white text-sm font-medium">
                                        <MathRenderer content={"|\\psi\\rangle = \\sum c_i |\\phi_i\\rangle"} mode="inline" />
                                    </span>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="text-xs font-medium text-slate-400">Physics</span>
                                </td>
                                <td className="px-8 py-5">
                                    <div className="flex items-center gap-2.5">
                                        <span className="size-2 rounded-full bg-neon-green shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
                                        <span className="text-xs font-bold text-neon-green uppercase tracking-wider">Indexed</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5 text-xs text-slate-500 font-medium">Oct 24, 2023</td>
                                <td className="px-8 py-5 text-right">
                                    <div className="flex justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                                        <button className="p-2 text-slate-400 hover:text-admin-primary transition-colors hover:bg-admin-primary/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">edit</span></button>
                                        <button className="p-2 text-slate-400 hover:text-red-400 transition-colors hover:bg-red-500/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">delete</span></button>
                                    </div>
                                </td>
                            </tr>
                            <tr className="hover:bg-admin-primary/5 transition-colors group">
                                <td className="px-8 py-5">
                                    <div className="flex flex-col gap-0.5">
                                        <span className="text-sm font-semibold text-slate-200 group-hover:text-slate-900 dark:text-white transition-colors">Binary Search Tree</span>
                                        <span className="text-[10px] font-mono text-slate-500 bg-white dark:bg-admin-bg-dark w-fit px-1.5 py-0.5 rounded border border-slate-200 dark:border-border-dark">CC-CS-5512</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="latex-white text-sm font-medium">
                                        <MathRenderer content={"O(\\log n)"} mode="inline" />
                                    </span>
                                </td>
                                <td className="px-8 py-5">
                                    <span className="text-xs font-medium text-slate-400">CS</span>
                                </td>
                                <td className="px-8 py-5">
                                    <div className="flex items-center gap-2.5">
                                        <span className="size-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
                                        <span className="text-xs font-bold text-red-500 uppercase tracking-wider">Failed</span>
                                    </div>
                                </td>
                                <td className="px-8 py-5 text-xs text-slate-500 font-medium">Oct 23, 2023</td>
                                <td className="px-8 py-5 text-right">
                                    <div className="flex justify-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                                        <button className="p-2 text-slate-400 hover:text-admin-primary transition-colors hover:bg-admin-primary/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">refresh</span></button>
                                        <button className="p-2 text-slate-400 hover:text-admin-primary transition-colors hover:bg-admin-primary/10 rounded-lg"><span className="material-symbols-outlined text-[20px]">edit</span></button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    <div className="px-8 py-5 flex justify-between items-center bg-white/40 dark:bg-white dark:bg-admin-bg-dark/40 border-t border-slate-200 dark:border-border-dark">
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Page 1 of 321 • 1,284 Records</span>
                        <div className="flex gap-1.5">
                            <button className="px-4 py-2 rounded border border-slate-200 dark:border-border-dark text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:bg-white dark:bg-admin-bg-dark hover:text-slate-900 dark:text-white transition-all disabled:opacity-50" disabled>Prev</button>
                            <button className="px-4 py-2 rounded bg-admin-primary text-white text-[10px] font-bold uppercase tracking-widest shadow-lg shadow-admin-primary/10">1</button>
                            <button className="px-4 py-2 rounded border border-slate-200 dark:border-border-dark text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:bg-white dark:bg-admin-bg-dark hover:text-slate-900 dark:text-white transition-all">2</button>
                            <button className="px-4 py-2 rounded border border-slate-200 dark:border-border-dark text-[10px] font-bold uppercase tracking-widest text-slate-400 hover:bg-white dark:bg-admin-bg-dark hover:text-slate-900 dark:text-white transition-all">Next</button>
                        </div>
                    </div>
                </div>
            </div>
            <footer className="h-12 border-t border-slate-200 dark:border-border-dark bg-white/90 dark:bg-white dark:bg-admin-bg-dark/90 backdrop-blur-sm flex items-center px-10 justify-between shrink-0">
                <div className="flex gap-10">
                    <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-[16px] text-neon-green">verified_user</span>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">INDEX HEALTH <span className="text-neon-green ml-1">99.98%</span></span>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-[16px] text-admin-primary">bolt</span>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">LATENCY <span className="text-slate-900 dark:text-white ml-1">12ms</span></span>
                    </div>
                    <div className="flex items-center gap-2.5">
                        <span className="material-symbols-outlined text-[16px] text-admin-primary">storage</span>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">DIMENSIONS <span className="text-slate-900 dark:text-white ml-1">1536d</span></span>
                    </div>
                </div>
                <div className="flex items-center gap-5">
                    <span className="text-[9px] font-bold tracking-[0.2em] text-slate-600">v2.4.5-STABLE</span>
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-neon-green/10 border border-neon-green/20">
                        <span className="size-1.5 rounded-full bg-neon-green"></span>
                        <span className="text-[9px] font-black text-neon-green">REALTIME</span>
                    </div>
                </div>
            </footer>
        </>
    );
}
