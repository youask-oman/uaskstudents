"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchTransferBalance, transferCredits, claimPendingCredits, CreditTransferBalance } from "@/lib/creditTransfer";
import { fetchNotifications, markNotificationRead, AppNotification } from "@/lib/notifications";

function makeIdempotencyKey() {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type Props = {
    onInfo?: (msg: string) => void;
};

export default function TransferAndNotificationsPanel({ onInfo }: Props) {
    const [balance, setBalance] = useState<CreditTransferBalance | null>(null);
    const [notifications, setNotifications] = useState<AppNotification[]>([]);
    const [loading, setLoading] = useState(false);
    const [recipientEmail, setRecipientEmail] = useState("");
    const [amount, setAmount] = useState(1);
    const [submitting, setSubmitting] = useState(false);

    const unreadCount = useMemo(() => notifications.filter((n) => !n.is_read).length, [notifications]);
    const hasUnread = unreadCount > 0;

    const refresh = async () => {
        setLoading(true);
        try {
            const [b, n] = await Promise.all([fetchTransferBalance(), fetchNotifications(undefined, 10)]);
            setBalance(b);
            setNotifications(n.items || []);
        } catch {
            // Silent by design on solve page.
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void refresh();
    }, []);

    useEffect(() => {
        const timer = window.setInterval(() => {
            void refresh();
        }, 30000);
        return () => window.clearInterval(timer);
    }, []);

    const handleTransfer = async () => {
        if (!recipientEmail.trim()) return;
        setSubmitting(true);
        try {
            const key = makeIdempotencyKey();
            const result = await transferCredits({
                recipient_email: recipientEmail.trim(),
                amount,
                idempotency_key: key,
            });
            onInfo?.(`Transfer ${result.status.toLowerCase()}: ${result.amount.toFixed(2)} credits`);
            setRecipientEmail("");
            await refresh();
        } catch (e) {
            onInfo?.(e instanceof Error ? e.message : "Transfer failed");
        } finally {
            setSubmitting(false);
        }
    };

    const handleClaim = async () => {
        setSubmitting(true);
        try {
            const result = await claimPendingCredits();
            if (result.claimed_count > 0) {
                onInfo?.(`Claimed ${result.claimed_count} pending transfer(s).`);
            }
            await refresh();
        } catch (e) {
            onInfo?.(e instanceof Error ? e.message : "Claim failed");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white">Transfer Credits</h4>
                    <span
                        className={`text-[10px] px-2 py-1 rounded-full font-semibold ${balance?.can_transfer ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}
                    >
                        {balance?.can_transfer ? "ENABLED" : "DISABLED"}
                    </span>
                </div>
                <p className="text-xs text-slate-500 mb-3">
                    {balance?.can_transfer
                        ? `Spendable: ${Number(balance.spendable_balance || 0).toFixed(2)} credits`
                        : balance?.reason_if_disabled || "Transfer unavailable"}
                </p>
                <div className="grid grid-cols-1 gap-2">
                    <input
                        type="email"
                        className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
                        placeholder="Recipient email"
                        value={recipientEmail}
                        onChange={(e) => setRecipientEmail(e.target.value)}
                        disabled={!balance?.can_transfer || submitting}
                    />
                    <input
                        type="number"
                        className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
                        value={amount}
                        min={Math.max(1, Number(balance?.min_transfer || 1))}
                        max={Number(balance?.max_transfer || 1000)}
                        onChange={(e) => setAmount(Number(e.target.value || 1))}
                        disabled={!balance?.can_transfer || submitting}
                    />
                    <button
                        className={`rounded-md px-3 py-2 text-sm font-semibold transition-colors ${balance?.can_transfer ? "bg-primary text-white hover:bg-primary/90 ring-2 ring-primary/30" : "bg-slate-200 text-slate-500"}`}
                        onClick={handleTransfer}
                        disabled={!balance?.can_transfer || submitting}
                    >
                        {submitting ? "Transferring..." : "Transfer Credits"}
                    </button>
                    <button
                        className="rounded-md px-3 py-2 text-sm font-medium border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200"
                        onClick={handleClaim}
                        disabled={submitting}
                    >
                        Claim Pending Transfers
                    </button>
                </div>
            </div>

            <div
                className={`border rounded-xl p-4 transition-colors ${
                    hasUnread
                        ? "bg-amber-50 dark:bg-amber-900/20 border-amber-300 dark:border-amber-700 animate-pulse"
                        : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                }`}
            >
                <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white">Notifications</h4>
                    <span className={`text-xs ${hasUnread ? "text-amber-700 dark:text-amber-300 font-bold" : "text-slate-500"}`}>
                        Unread: {unreadCount}
                    </span>
                </div>
                {loading ? (
                    <p className="text-xs text-slate-500">Loading…</p>
                ) : notifications.length === 0 ? (
                    <p className="text-xs text-slate-500">No notifications</p>
                ) : (
                    <div className="space-y-2 max-h-56 overflow-auto pr-1">
                        {notifications.map((n) => (
                            <button
                                key={n.id}
                                className={`w-full text-left rounded-md border px-2 py-2 text-xs ${n.is_read ? "border-slate-200 dark:border-slate-700" : "border-amber-400 bg-amber-100/70 dark:bg-amber-900/30 animate-pulse"}`}
                                onClick={async () => {
                                    try {
                                        await markNotificationRead(n.id);
                                        await refresh();
                                    } catch {
                                        // noop
                                    }
                                }}
                            >
                                <div className="font-semibold text-slate-800 dark:text-slate-100">{n.title}</div>
                                <div className="text-slate-600 dark:text-slate-300">{n.body}</div>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

