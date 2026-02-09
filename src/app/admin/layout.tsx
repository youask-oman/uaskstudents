"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type AdminProfile = {
    name: string;
    role: string;
    avatar?: string;
    authorized: boolean;
};

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const router = useRouter();
    const [adminProfile, setAdminProfile] = useState<AdminProfile>({
        name: "Admin User",
        role: "",
        avatar: "",
        authorized: false,
    });

    useEffect(() => {
        if (typeof window === "undefined") {
            router.push("/login");
            return;
        }
        const role = localStorage.getItem("user_role") ?? "";
        const profile: AdminProfile = {
            name: localStorage.getItem("user_name") ?? "Admin User",
            role: role,
            avatar: localStorage.getItem("user_avatar") ?? "",
            authorized: role === "admin",
        };

        // Defer update to avoid synchronous state update warning
        setTimeout(() => {
            setAdminProfile(prev => {
                if (JSON.stringify(prev) !== JSON.stringify(profile)) {
                    return profile;
                }
                return prev;
            });
        }, 0);

        if (!profile.authorized) {
            router.push("/login");
        }
    }, [pathname, router]);
    if (!adminProfile.authorized) return null;

    const adminRoleLabel = adminProfile.authorized ? "Platform Administrator" : "Super Admin";

    const navItems = [
        { label: "Overview", href: "/admin/dashboard", icon: "dashboard" },
        { label: "Users", href: "/admin/users", icon: "group" },
        { label: "Quotas", href: "/admin/quotas", icon: "speed" },
        { label: "Subscriptions", href: "/admin/subscriptions", icon: "diamond" },
        { label: "Prompt Registry", href: "/admin/prompt-registry", icon: "terminal" },
        { label: "Schema Registry", href: "/admin/schema-registry", icon: "data_object" },
        { label: "Prompt Bindings", href: "/admin/prompt-bindings", icon: "link" },
        { label: "Content", href: "/admin/content", icon: "collections_bookmark" },
        { label: "WhatsApp Bot", href: "/admin/whatsapp-bot", icon: "chat" },
        { label: "WhatsApp Monitor", href: "/admin/whatsapp-monitor", icon: "monitor_heart" },
        { label: "Logs", href: "/admin/logs", icon: "receipt_long" },
        { label: "Solvers", href: "/admin/solver-attempts", icon: "article" },
        { label: "Payments Overview", href: "/adminpayments", icon: "payments" },
        { label: "Requests & Cost", href: "/adminpayments/requests", icon: "request_quote" },
        { label: "Top-Ups", href: "/adminpayments/topups", icon: "credit_card" },
        { label: "Data", href: "/admin/data", icon: "table_view" },
        { label: "System Config", href: "/admin/system-config", icon: "tune" },
        // Billing Admin Section
        { label: "─────────────", href: "#", icon: "" },
        { label: "Billing Flags", href: "/admin/billing/flags", icon: "toggle_on" },
        { label: "Credit Programs", href: "/admin/billing/programs", icon: "card_giftcard" },
        { label: "Holds", href: "/admin/billing/holds", icon: "pause_circle" },
        { label: "Refunds", href: "/admin/billing/refunds", icon: "currency_exchange" },
        { label: "Health", href: "/admin/billing/health", icon: "monitor_heart" },
        { label: "Ledger", href: "/admin/billing/ledger", icon: "menu_book" },
        { label: "Invoices", href: "/admin/billing/invoices", icon: "receipt" },
    ];


    return (
        <div
            suppressHydrationWarning
            className="font-admin bg-background-light text-slate-900 dark:bg-background-dark dark:text-slate-200 min-h-screen flex overflow-hidden transition-colors"
        >
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 bg-white dark:bg-[#111827] border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between p-4 transition-colors">
                <div className="flex flex-col gap-8">
                    <div className="flex items-center gap-3 px-2">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src="/logo-dark.png" alt="uask.ai" className="h-8 w-auto" />
                        <div className="flex flex-col">
                            <h1 className="text-slate-900 dark:text-white text-base font-bold leading-none">uask.ai</h1>
                            <p className="text-slate-500 text-[10px] uppercase tracking-widest font-semibold mt-1">Admin Panel</p>
                        </div>
                    </div>
                    <nav className="flex flex-col gap-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${pathname === item.href
                                    ? "bg-admin-primary text-white shadow-lg shadow-admin-primary/20"
                                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
                                    }`}
                            >
                                <span className={`material-symbols-outlined ${pathname === item.href ? "fill-current" : ""}`}>
                                    {item.icon}
                                </span>
                                <p className="text-sm font-medium">{item.label}</p>
                            </Link>
                        ))}
                    </nav>
                </div>
                <div className="flex flex-col gap-4">
                    <button className="w-full py-2.5 bg-admin-primary hover:bg-admin-primary/90 text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-admin-primary/20 flex items-center justify-center gap-2">
                        <span className="material-symbols-outlined text-sm">add</span>
                        New Report
                    </button>
                    <div className="flex items-center gap-3 px-2 py-2 border-t border-slate-200 dark:border-slate-800 pt-4">
                        <div className="size-8 rounded-full bg-slate-200 dark:bg-slate-700 bg-cover bg-center overflow-hidden flex items-center justify-center border border-slate-200 dark:border-slate-700 shadow-sm">
                            {adminProfile.avatar ? (
                                <>
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src={adminProfile.avatar} alt={adminProfile.name} className="w-full h-full object-cover" />
                                </>
                            ) : (
                                <span className="text-[10px] font-bold text-admin-primary">{adminProfile.name.split(' ').map(n => n[0]).join('')}</span>
                            )}
                        </div>
                        <div className="flex flex-col">
                            <p className="text-slate-900 dark:text-white text-xs font-bold truncate max-w-[120px]">{adminProfile.name}</p>
                            <p className="text-slate-500 text-[10px]">{adminRoleLabel}</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content Shell */}
            <main className="flex-1 flex flex-col overflow-y-auto w-full">
                {children}
            </main>
        </div>
    );
}
