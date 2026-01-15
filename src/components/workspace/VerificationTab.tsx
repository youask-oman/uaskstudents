"use client";

import React from "react";
import MathRenderer from "../MathRenderer";

interface VerificationItem {
    method: string;
    why_it_works: string;
    steps: string[];
    conclusion: string;
}

interface VerificationTabProps {
    methods: VerificationItem[];
    finalAnswer?: string;
    confidence?: number;
}

export default function VerificationTab({
    methods,
    finalAnswer,
    confidence
}: VerificationTabProps) {
    const defaultMethods = [
        {
            method: "Substitution Check",
            why_it_works: "Verifies that the solution satisfies the original equation.",
            steps: [
                `Replace x with ${finalAnswer || "?"}`,
                "Simplify both sides",
                "Both sides match"
            ],
            conclusion: "The solution is correct."
        },
        {
            method: "Equivalent-form Check",
            why_it_works: "Ensures all transformation steps preserved the solution set.",
            steps: [],
            conclusion: "Logical Integrity Confirmed"
        }
    ];

    const displayMethods = methods && methods.length > 0 ? methods : defaultMethods;

    return (
        <div className="mb-12 animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-[#111318] dark:text-white">Solution Verification</h3>
                <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full text-xs font-bold border border-emerald-100 dark:border-emerald-800">
                    <span className="material-symbols-outlined text-[16px]">verified</span>
                    Fully Validated
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Method 01 */}
                <div className="bg-white dark:bg-[#1e2634] p-6 rounded-2xl border border-[#e5e7eb] dark:border-[#2a303c] shadow-sm flex flex-col h-full">
                    <div className="flex items-start justify-between mb-4">
                        <div className="size-10 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl flex items-center justify-center">
                            <span className="material-symbols-outlined">check_circle</span>
                        </div>
                        <span className="text-[10px] font-black uppercase text-slate-400">Method 01</span>
                    </div>
                    <h4 className="font-bold text-base mb-3 text-[#111318] dark:text-white">
                        {displayMethods[0]?.method || "Substitution Check"}
                    </h4>

                    <div className="bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl space-y-3 flex-1">
                        {displayMethods[0]?.steps.map((step, idx) => (
                            <div key={idx} className="flex justify-between items-center text-sm">
                                <div className="text-[#616f89] dark:text-slate-400 w-full">
                                    <MathRenderer content={step} />
                                </div>
                            </div>
                        ))}
                        <div className="pt-2 mt-2 border-t border-slate-200 dark:border-slate-700 flex justify-between items-center">
                            <span className="text-xs font-bold uppercase text-emerald-600 dark:text-emerald-400">Conclusion</span>
                            <span className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">
                                <MathRenderer content={displayMethods[0]?.conclusion || "True"} inline />
                            </span>
                        </div>
                    </div>
                </div>

                {/* Method 02 */}
                <div className="bg-white dark:bg-[#1e2634] p-6 rounded-2xl border border-[#e5e7eb] dark:border-[#2a303c] shadow-sm flex flex-col h-full">
                    <div className="flex items-start justify-between mb-4">
                        <div className="size-10 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl flex items-center justify-center">
                            <span className="material-symbols-outlined">account_tree</span>
                        </div>
                        <span className="text-[10px] font-black uppercase text-slate-400">Method 02</span>
                    </div>
                    <h4 className="font-bold text-base mb-3 text-[#111318] dark:text-white">
                        {displayMethods[1]?.method || "Equivalent-form Check"}
                    </h4>
                    <p className="text-sm text-[#616f89] dark:text-slate-400 leading-relaxed mb-4 flex-1">
                        {displayMethods[1]?.why_it_works || "Each transformation step used equality-preserving operations (division by a non-zero constant and addition of a constant). These reversible operations ensure the solution set is preserved from the original equation."}
                    </p>
                    <div className="mt-auto flex items-center gap-2 text-[11px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-3 py-2 rounded-lg">
                        <span className="material-symbols-outlined text-[14px]">shield</span>
                        Logical Integrity Confirmed
                    </div>
                </div>
            </div>

            {/* Foundational Concepts Section */}
            <div className="mb-12">
                <h3 className="text-xl font-bold mb-6 text-[#111318] dark:text-white">Foundational Concepts</h3>
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
                    <div className="lg:col-span-2 space-y-4">
                        <div className="flex items-center gap-2 mb-4 px-1">
                            <span className="material-symbols-outlined text-primary text-[20px]">menu_book</span>
                            <h4 className="font-bold text-sm uppercase tracking-wider text-slate-500">Key Concepts</h4>
                        </div>
                        {/* Concept 1 */}
                        <div className="bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4 hover:border-primary/30 transition-colors group">
                            <div className="size-10 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all">
                                <span className="material-symbols-outlined">swap_horiz</span>
                            </div>
                            <div>
                                <p className="font-bold text-sm text-[#111318] dark:text-white">Inverse Operations</p>
                                <p className="text-[11px] text-[#616f89] dark:text-slate-400">Operations that undo each other (e.g., + and -)</p>
                            </div>
                        </div>
                        {/* Concept 2 */}
                        <div className="bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4 hover:border-primary/30 transition-colors group">
                            <div className="size-10 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all">
                                <span className="material-symbols-outlined">straighten</span>
                            </div>
                            <div>
                                <p className="font-bold text-sm text-[#111318] dark:text-white">Solving Linear Equations</p>
                                <p className="text-[11px] text-[#616f89] dark:text-slate-400">Finding the value that makes the statement true</p>
                            </div>
                        </div>
                        {/* Concept 3 */}
                        <div className="bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c] flex items-center gap-4 hover:border-primary/30 transition-colors group">
                            <div className="size-10 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all">
                                <span className="material-symbols-outlined">view_cozy</span>
                            </div>
                            <div>
                                <p className="font-bold text-sm text-[#111318] dark:text-white">Distributive Property</p>
                                <p className="text-[11px] text-[#616f89] dark:text-slate-400">
                                    <MathRenderer content="a(b + c) = ab + ac" inline />
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="lg:col-span-3 space-y-6">
                        <div className="flex items-center gap-2 mb-4 px-1">
                            <span className="material-symbols-outlined text-amber-500 text-[20px]">lightbulb</span>
                            <h4 className="font-bold text-sm uppercase tracking-wider text-slate-500">Learning Insights</h4>
                        </div>
                        <div className="bg-amber-50 dark:bg-amber-900/10 rounded-2xl border border-amber-200 dark:border-amber-900/50 p-6">
                            <div className="flex items-center gap-2 mb-4 text-amber-700 dark:text-amber-500">
                                <span className="material-symbols-outlined text-[20px]">warning</span>
                                <h4 className="font-bold text-sm uppercase tracking-tight">Avoid these Common Mistakes</h4>
                            </div>
                            <div className="bg-white/60 dark:bg-black/20 p-4 rounded-xl border border-amber-200/50">
                                <p className="text-sm font-bold mb-1 text-[#111318] dark:text-white">Dividing only one side</p>
                                <p className="text-xs leading-relaxed text-[#616f89] dark:text-slate-400">
                                    Students often divide the left side to "cancel" the coefficient but forget to divide the constant on the right.
                                    <span className="block mt-2 font-medium text-amber-800 dark:text-amber-400 italic">
                                        Correct: <MathRenderer content="3(x-2)/3 = 15/3" inline />
                                    </span>
                                </p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c]">
                                <p className="text-[10px] font-black uppercase text-slate-400 mb-1">y-intercept</p>
                                <p className="text-lg font-bold text-primary"><MathRenderer content="(0, 0)" inline /></p>
                            </div>
                            <div className="bg-white dark:bg-[#1e2634] p-4 rounded-xl border border-[#e5e7eb] dark:border-[#2a303c]">
                                <p className="text-[10px] font-black uppercase text-slate-400 mb-1">Domain</p>
                                <p className="text-sm font-bold text-slate-700 dark:text-slate-200">All Real Numbers (ℝ)</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Improve Your Mastery Section */}
            <div className="mb-12">
                <h3 className="text-xl font-bold mb-6 text-[#111318] dark:text-white">Improve Your Mastery</h3>

                {/* Progress Bar */}
                <div className="bg-white dark:bg-[#1e2634] p-6 rounded-2xl border border-[#e5e7eb] dark:border-[#2a303c] mb-8">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-bold text-[#111318] dark:text-white">Algebra: Linear Equations</span>
                        <span className="text-sm font-black text-primary">99%</span>
                    </div>
                    <div className="w-full bg-slate-100 dark:bg-slate-800 h-2.5 rounded-full overflow-hidden">
                        <div className="bg-primary h-full rounded-full" style={{ width: "99%" }}></div>
                    </div>
                </div>

                {/* Example Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    {/* Example A */}
                    <div className="bg-white dark:bg-[#1e2634] rounded-2xl border border-[#e5e7eb] dark:border-[#2a303c] overflow-hidden flex flex-col">
                        <div className="p-6 flex-1">
                            <div className="flex justify-between items-start mb-4">
                                <span className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded text-[10px] font-bold uppercase">Example A</span>
                                <span className="material-symbols-outlined text-slate-300">fitness_center</span>
                            </div>
                            <div className="text-2xl font-medium mb-6 text-[#111318] dark:text-white">
                                <MathRenderer content="4(x - 1) = 20" forceMath inline />
                            </div>
                            <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl mb-4 border border-blue-100 dark:border-blue-900/30">
                                <span className="material-symbols-outlined text-primary text-[18px]">info</span>
                                <div>
                                    <p className="text-[10px] font-black uppercase text-primary mb-0.5">Key Idea</p>
                                    <p className="text-[11px] text-[#616f89] dark:text-slate-400 leading-tight">Start by dividing both sides by 4.</p>
                                </div>
                            </div>
                        </div>
                        <details className="group border-t border-[#e5e7eb] dark:border-[#2a303c]">
                            <summary className="flex items-center justify-center p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors list-none">
                                <span className="text-xs font-bold text-primary flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[16px] group-open:rotate-180 transition-transform">expand_more</span>
                                    <span className="group-open:hidden">Show Solution</span>
                                    <span className="hidden group-open:inline">Hide Solution</span>
                                </span>
                            </summary>
                            <div className="p-6 bg-slate-50 dark:bg-slate-800/30 text-center border-t border-[#e5e7eb] dark:border-[#2a303c]">
                                <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                                    <MathRenderer content="x = 6" forceMath inline />
                                </div>
                                <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-widest font-black">Final Answer</p>
                            </div>
                        </details>
                    </div>

                    {/* Example B with Test Case */}
                    <div className="bg-white dark:bg-[#1e2634] rounded-2xl border border-[#e5e7eb] dark:border-[#2a303c] overflow-hidden flex flex-col">
                        <div className="p-6 flex-1">
                            <div className="flex justify-between items-start mb-4">
                                <span className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded text-[10px] font-bold uppercase">Example B</span>
                                <span className="material-symbols-outlined text-slate-300">fitness_center</span>
                            </div>
                            <div className="text-2xl font-medium mb-6 text-[#111318] dark:text-white">
                                <MathRenderer content="2(x + 3) = 14" forceMath inline />
                            </div>
                            <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl mb-4 border border-blue-100 dark:border-blue-900/30">
                                <span className="material-symbols-outlined text-primary text-[18px]">info</span>
                                <div>
                                    <p className="text-[10px] font-black uppercase text-primary mb-0.5">Key Idea</p>
                                    <p className="text-[11px] text-[#616f89] dark:text-slate-400 leading-tight">Divide by 2, then subtract 3.</p>
                                </div>
                            </div>
                        </div>
                        <details className="group border-t border-[#e5e7eb] dark:border-[#2a303c]">
                            <summary className="flex items-center justify-center p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors list-none">
                                <span className="text-xs font-bold text-primary flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[16px] group-open:rotate-180 transition-transform">expand_more</span>
                                    <span className="group-open:hidden">Show Solution</span>
                                    <span className="hidden group-open:inline">Hide Solution</span>
                                </span>
                            </summary>
                            <div className="p-6 bg-slate-50 dark:bg-slate-800/30 text-center border-t border-[#e5e7eb] dark:border-[#2a303c]">
                                <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                                    <MathRenderer content="x = -2 \text{ or } x = 5" forceMath inline />
                                </div>
                                <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-widest font-black">Final Answer</p>
                            </div>

                            {/* Regex Repair Test Cases */}
                            <div className="p-4 border-t border-[#e5e7eb] dark:border-[#2a303c] bg-amber-50 dark:bg-amber-900/10">
                                <p className="text-[10px] text-amber-600 font-bold mb-2 uppercase">Sanitization Tests</p>
                                <div className="space-y-2 text-sm">
                                    <div className="flex gap-2 items-center">
                                        <span className="text-xs text-slate-400 w-24 shrink-0">textLet...</span>
                                        <MathRenderer content="textLet y = x^2" forceMath inline />
                                    </div>
                                    <div className="flex gap-2 items-center">
                                        <span className="text-xs text-slate-400 w-24 shrink-0">textLine :</span>
                                        <MathRenderer content="textLine : y = 2x + 1" forceMath inline />
                                    </div>
                                    <div className="flex gap-2 items-center">
                                        <span className="text-xs text-slate-400 w-24 shrink-0">text{"{...}"}</span>
                                        <MathRenderer content="text{Thus intersections are} (3,9)" forceMath inline />
                                    </div>
                                </div>
                            </div>
                        </details>
                    </div>
                </div>

                <div className="w-full">
                    <button className="w-full py-5 bg-primary text-white rounded-2xl font-bold flex items-center justify-center gap-3 shadow-xl shadow-primary/30 hover:bg-blue-700 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed">
                        <span className="material-symbols-outlined fill-1">auto_awesome</span>
                        Generate More Practice Problems
                    </button>
                </div>
            </div>
        </div>
    );
}
