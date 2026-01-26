"use client";

import SystemConfigPanel from "@/components/admin/SystemConfigPanel";

export default function AdminSystemConfigPage() {
    return (
        <div className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
            <header className="space-y-2">
                <p className="text-sm uppercase tracking-[0.4em] text-slate-400">Admin</p>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">System Configuration</h1>
                <p className="text-sm text-slate-500">Manage token limits and other flags stored in the SystemConfig table.</p>
            </header>
            <SystemConfigPanel />
        </div>
    );
}
