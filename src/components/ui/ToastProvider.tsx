"use client";

import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

export type ToastType = "success" | "error" | "info";

export type ToastPayload = {
    type: ToastType;
    title: string;
    message?: string;
    requestId?: string;
    durationMs?: number;
};

type ToastItem = ToastPayload & { id: string };

type ToastContextValue = {
    pushToast: (toast: ToastPayload) => void;
    dismissToast: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const makeId = () => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

function ToastViewport({
    toasts,
    onDismiss,
}: {
    toasts: ToastItem[];
    onDismiss: (id: string) => void;
}) {
    return (
        <div className="fixed right-4 top-4 z-[100] flex w-[360px] max-w-[92vw] flex-col gap-3">
            {toasts.map((toast) => {
                const accent =
                    toast.type === "success"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                        : toast.type === "error"
                            ? "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300"
                            : "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-200";

                return (
                    <div
                        key={toast.id}
                        className={`rounded-2xl border px-4 py-3 shadow-xl backdrop-blur-md ${accent}`}
                        role="status"
                    >
                        <div className="flex items-start justify-between gap-3">
                            <div className="flex-1">
                                <p className="text-sm font-bold">{toast.title}</p>
                                {toast.message && (
                                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                                        {toast.message}
                                    </p>
                                )}
                                {toast.requestId && (
                                    <p className="mt-1 text-[10px] uppercase tracking-widest text-slate-500">
                                        request_id: {toast.requestId}
                                    </p>
                                )}
                            </div>
                            <button
                                onClick={() => onDismiss(toast.id)}
                                className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                                aria-label="Dismiss notification"
                            >
                                <span className="material-symbols-outlined text-[18px]">close</span>
                            </button>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const dismissToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, []);

    const pushToast = useCallback(
        (toast: ToastPayload) => {
            const id = makeId();
            const entry: ToastItem = { ...toast, id };
            setToasts((prev) => [...prev, entry]);
            const duration =
                toast.durationMs ?? (toast.type === "error" ? 9000 : 5200);
            if (duration > 0) {
                window.setTimeout(() => dismissToast(id), duration);
            }
        },
        [dismissToast]
    );

    const value = useMemo(() => ({ pushToast, dismissToast }), [pushToast, dismissToast]);

    return (
        <ToastContext.Provider value={value}>
            {children}
            <ToastViewport toasts={toasts} onDismiss={dismissToast} />
        </ToastContext.Provider>
    );
}

export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error("useToast must be used within a ToastProvider.");
    }
    return context;
}

export function useToastOptional() {
    return useContext(ToastContext);
}
