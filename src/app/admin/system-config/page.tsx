"use client";

import Link from "next/link";

export default function AdminSystemConfigPage() {
    return (
        <div className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">System Configuration</h1>
                <p className="text-sm text-slate-500">SystemConfig is deprecated. Runtime config now comes from prompt bindings, OCR configuration, and environment variables.</p>
            </header>
            <section className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-3">
                <p className="text-sm text-slate-700 dark:text-slate-200">
                    Use these pages instead:
                </p>
                <ul className="list-disc pl-6 text-sm text-slate-700 dark:text-slate-200 space-y-1">
                    <li>
                        Prompt bindings: <Link className="text-cyan-700 dark:text-cyan-300" href="/admin/prompt-bindings">/admin/prompt-bindings</Link>
                    </li>
                    <li>
                        OCR configuration: <Link className="text-cyan-700 dark:text-cyan-300" href="/admin/ocr-configuration">/admin/ocr-configuration</Link>
                    </li>
                    <li>
                        Environment variables: `.env` / deployment environment.
                    </li>
                </ul>
            </section>
        </div>
    );
}
