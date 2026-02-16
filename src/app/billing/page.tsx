"use client";

import { Suspense, useEffect, useState } from "react";
import DashboardNavBar from "@/components/DashboardNavBar";
import { useToast } from "@/components/ui/ToastProvider";
import {
    fetchWalletLedger,
    fetchWalletLots,
    fetchWalletPrograms,
    fetchWalletSummary,
    WalletLedgerEntry,
    WalletLot,
    WalletProgramEnrollment,
    WalletSummary,
} from "@/lib/wallet";
import { API_BASE_URL, parseApiError } from "@/lib/api";

const PAGE_TITLE = "Wallet & Programs";

export const dynamic = "force-dynamic";

type Invoice = {
    id: number;
    invoice_number: string;
    kind: string;
    status: string;
    total_amount: number;
    currency: string;
    created_at: string;
};

export default function BillingPage() {
    const { pushToast } = useToast();
    const [wallet, setWallet] = useState<WalletSummary | null>(null);
    const [lots, setLots] = useState<WalletLot[]>([]);
    const [ledger, setLedger] = useState<WalletLedgerEntry[]>([]);
    const [programs, setPrograms] = useState<WalletProgramEnrollment[]>([]);
    const [invoices, setInvoices] = useState<Invoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [openingInvoiceId, setOpeningInvoiceId] = useState<number | null>(null);

    const redirectToLogin = () => {
        if (typeof window === "undefined") return;
        window.location.href = `/login?redirect=${encodeURIComponent("/billing")}`;
    };

    const isAuthError = (error: unknown): boolean => {
        if (!(error instanceof Error)) return false;
        const message = error.message.toLowerCase();
        return (
            message.includes("log in") ||
            message.includes("login") ||
            message.includes("unauthorized") ||
            message.includes("missing token") ||
            message.includes("forbidden")
        );
    };

    const handleOpenInvoice = async (invoiceId: number) => {
        const token = localStorage.getItem("token");
        if (!token) {
            redirectToLogin();
            return;
        }
        setOpeningInvoiceId(invoiceId);
        try {
            const res = await fetch(`${API_BASE_URL}/api/v1/billing/invoices/${invoiceId}/html`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Invoice unavailable",
                    message: err.message,
                    requestId: err.requestId,
                });
                return;
            }
            const html = await res.text();
            const blob = new Blob([html], { type: "text/html" });
            const url = URL.createObjectURL(blob);
            window.open(url, "_blank", "noopener,noreferrer");
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (error) {
            pushToast({
                type: "error",
                title: "Invoice unavailable",
                message: error instanceof Error ? error.message : "Unexpected error",
            });
        } finally {
            setOpeningInvoiceId(null);
        }
    };

    useEffect(() => {
        const loadData = async () => {
            const token = localStorage.getItem("token");
            if (!token) {
                redirectToLogin();
                return;
            }
            try {
                const [summary, lotResp, ledgerResp, programResp] = await Promise.all([
                    fetchWalletSummary(),
                    fetchWalletLots(12, 0),
                    fetchWalletLedger(12, 0),
                    fetchWalletPrograms(50, 0),
                ]);
                setWallet(summary);
                setLots(lotResp.items || []);
                setLedger(ledgerResp.items || []);
                setPrograms(programResp.items || []);
            } catch (error) {
                if (isAuthError(error)) {
                    redirectToLogin();
                    return;
                }
                pushToast({
                    type: "error",
                    title: "Failed to load wallet",
                    message:
                        error instanceof Error
                            ? error.message
                            : "We couldn't load your wallet right now. Please try again.",
                });
            }

            try {
                const res = await fetch(`${API_BASE_URL}/api/v1/billing/invoices`, {
                    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
                });
                if (!res.ok) {
                    const err = await parseApiError(res);
                    if (
                        err.status === 401 ||
                        err.status === 403 ||
                        (err.code || "").toLowerCase() === "auth_required"
                    ) {
                        redirectToLogin();
                        return;
                    }
                    pushToast({
                        type: "error",
                        title: "Failed to load invoices",
                        message: err.message || "Unable to load invoice history right now.",
                        requestId: err.requestId,
                    });
                } else {
                    const data = await res.json();
                    setInvoices(Array.isArray(data) ? data : []);
                }
            } catch (error) {
                if (isAuthError(error)) {
                    redirectToLogin();
                    return;
                }
                pushToast({
                    type: "error",
                    title: "Failed to load invoices",
                    message:
                        error instanceof Error
                            ? error.message
                            : "We couldn't load your invoices right now. Please try again.",
                });
            } finally {
                setLoading(false);
            }
        };

        void loadData();
    }, [pushToast]);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
            <Suspense fallback={<div className="h-16 w-full" />}>
                <DashboardNavBar />
            </Suspense>

            <main className="max-w-5xl mx-auto px-4 py-12 space-y-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">{PAGE_TITLE}</h1>
                    <p className="text-slate-500 dark:text-slate-400">
                        View your credit balance, active programs, and top-up history.
                    </p>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6">
                        <div>
                            <p className="text-xs font-bold text-primary uppercase tracking-widest">Wallet Summary</p>
                            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                                {wallet ? wallet.spendable_balance.toFixed(2) : "--"} credits
                            </h2>
                            <p className="text-sm text-slate-500 mt-1">
                                Cached: {wallet ? wallet.cached_balance.toFixed(2) : "--"} | Delta {wallet ? wallet.delta.toFixed(2) : "--"}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800 rounded-xl">
                                <p className="text-xs text-slate-500 uppercase">Holds</p>
                                <p className="text-sm font-semibold">{wallet ? wallet.pending_holds : "--"}</p>
                                <p className="text-[11px] text-slate-400">{wallet ? wallet.pending_hold_credits.toFixed(2) : "--"} credits</p>
                            </div>
                            <div className="px-4 py-3 bg-slate-50 dark:bg-slate-800 rounded-xl">
                                <p className="text-xs text-slate-500 uppercase">Expiring Soon</p>
                                <p className="text-sm font-semibold">{wallet ? wallet.expiring_soon_lots : "--"} lots</p>
                                <p className="text-[11px] text-slate-400">{wallet ? wallet.expiring_soon_credits.toFixed(2) : "--"} credits</p>
                            </div>
                            <a
                                href="/billing/payment"
                                className="px-4 py-3 bg-primary text-white rounded-xl text-sm font-semibold flex items-center gap-2"
                            >
                                <span className="material-symbols-outlined text-[18px]">add_card</span>
                                Top Up Credits
                            </a>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Credit Programs</h3>
                        {programs.length === 0 ? (
                            <p className="text-sm text-slate-500">No active programs.</p>
                        ) : (
                            <div className="space-y-3">
                                {programs.map((program) => (
                                    <div key={program.id} className="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                                                    {program.program_name || program.program_slug}
                                                </p>
                                                <p className="text-xs text-slate-500">Status: {program.status}</p>
                                            </div>
                                            {program.monthly_gift_credits && (
                                                <span className="text-xs font-semibold text-primary">
                                                    {program.monthly_gift_credits.toFixed(0)} credits / month
                                                </span>
                                            )}
                                        </div>
                                        {program.next_grant_date && (
                                            <p className="text-[11px] text-slate-400 mt-1">
                                                Next grant: {new Date(program.next_grant_date).toLocaleDateString()} ({program.next_grant_status})
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Recent Ledger Activity</h3>
                        {ledger.length === 0 ? (
                            <p className="text-sm text-slate-500">No ledger activity yet.</p>
                        ) : (
                            <ul className="space-y-3">
                                {ledger.map((entry) => (
                                    <li key={entry.id} className="flex items-center justify-between text-sm">
                                        <div>
                                            <p className="font-semibold text-slate-900 dark:text-white">{entry.event_type}</p>
                                            <p className="text-xs text-slate-500">{new Date(entry.created_at).toLocaleString()}</p>
                                        </div>
                                        <span className={`font-semibold ${entry.credits_delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                                            {entry.credits_delta >= 0 ? "+" : ""}{entry.credits_delta.toFixed(2)}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Credit Lots</h3>
                        <span className="text-xs text-slate-500">Showing {lots.length} recent lots</span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                                <tr>
                                    <th className="px-6 py-3 text-xs font-bold text-slate-400 uppercase">Source</th>
                                    <th className="px-6 py-3 text-xs font-bold text-slate-400 uppercase">Type</th>
                                    <th className="px-6 py-3 text-xs font-bold text-slate-400 uppercase">Remaining</th>
                                    <th className="px-6 py-3 text-xs font-bold text-slate-400 uppercase">Expires</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {lots.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-6 text-center text-sm text-slate-500">
                                            No credit lots yet.
                                        </td>
                                    </tr>
                                ) : (
                                    lots.map((lot) => (
                                        <tr key={lot.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                            <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                                                {lot.source_label || "Credits"}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                                                {lot.lot_type || "TOPUP"}
                                            </td>
                                            <td className="px-6 py-4 text-sm font-semibold text-slate-900 dark:text-white">
                                                {lot.credits_remaining.toFixed(2)} / {lot.credits_total.toFixed(2)}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-slate-500">
                                                {lot.expires_at ? new Date(lot.expires_at).toLocaleDateString() : "No expiry"}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div className="space-y-4">
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">Invoices & Receipts</h3>

                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
                        {loading ? (
                            <div className="p-12 text-center text-slate-500">Loading history...</div>
                        ) : invoices.length === 0 ? (
                            <div className="p-12 text-center text-slate-500">No invoices found.</div>
                        ) : (
                            <table className="w-full text-left">
                                <thead className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                                    <tr>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Date</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Invoice #</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase">Amount</th>
                                        <th className="px-6 py-4 text-xs font-bold text-slate-400 uppercase text-right">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {invoices.map((inv) => (
                                        <tr key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                            <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                                                {new Date(inv.created_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4 text-sm font-mono text-slate-900 dark:text-white">
                                                {inv.invoice_number}
                                            </td>
                                            <td className="px-6 py-4 text-sm font-bold text-slate-900 dark:text-white">
                                                {inv.currency === "USD" ? "$" : ""}{inv.total_amount.toFixed(2)}
                                            </td>
                                            <td className="px-6 py-4 text-right flex items-center justify-end gap-3">
                                                <button
                                                    type="button"
                                                    onClick={() => handleOpenInvoice(inv.id)}
                                                    className="text-primary hover:text-primary-hover font-medium text-xs transition-colors disabled:opacity-60"
                                                    disabled={openingInvoiceId === inv.id}
                                                >
                                                    {openingInvoiceId === inv.id ? "Opening..." : "View"}
                                                </button>
                                                <span className={`inline-flex px-2 py-1 rounded text-xs font-bold uppercase ${inv.status === "PAID"
                                                    ? "bg-green-100 text-green-700"
                                                    : "bg-slate-100 text-slate-600"
                                                    }`}>
                                                    {inv.status}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
