"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ToastProvider } from "@/components/ui/ToastProvider";

type AdminProfile = {
    name: string;
    role: string;
    avatar?: string;
    authorized: boolean;
};

export default function AdminPaymentsLayout({
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
        const token = localStorage.getItem("token");
        const role = localStorage.getItem("user_role") ?? "";
        const profile: AdminProfile = {
            name: localStorage.getItem("user_name") ?? "Admin User",
            role: role,
            avatar: localStorage.getItem("user_avatar") ?? "",
            authorized: (role === "admin" || role === "superadmin") && !!token,
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

    const navItems = [
        { label: "Overview", href: "/adminpayments", icon: "monitoring" },
        { label: "Requests", href: "/adminpayments/requests", icon: "table_view" },
        { label: "Top-Ups", href: "/adminpayments/topups", icon: "add_card" },
        { label: "Legacy Subscriptions", href: "/adminpayments/subscriptions", icon: "card_membership" },
        { label: "Invoices", href: "/adminpayments?tab=invoices", icon: "receipt" },
        { label: "Stripe Events", href: "/adminpayments?tab=stripe_events", icon: "receipt_long" },
        { label: "Reconciliation", href: "/adminpayments?tab=reconciliation", icon: "balance" },
        { label: "Pricing", href: "/adminpayments?tab=pricing", icon: "price_change" },
        { label: "Payments Config", href: "/adminpayments/config", icon: "settings" },
        { label: "Back to Main Admin", href: "/admin/dashboard", icon: "arrow_back" },
    ];

    return (
        <ToastProvider>
            <div
                suppressHydrationWarning
                className="font-admin bg-background-light text-slate-900 dark:bg-background-dark dark:text-slate-200 min-h-screen flex overflow-hidden transition-colors"
            >
                {/* Sidebar */}
                <aside className="w-64 flex-shrink-0 bg-slate-900 text-white border-r border-slate-800 flex flex-col justify-between p-4 transition-colors">
                    <div className="flex flex-col gap-8">
                        <div className="flex items-center gap-3 px-2">
                            <Image
                                src="/logo-dark.png"
                                alt="uask.ai"
                                width={96}
                                height={32}
                                className="h-8 w-auto invert brightness-0 grayscale-0"
                                style={{ filter: "brightness(0) invert(1)" }}
                                priority
                            />
                            <div className="flex flex-col">
                                <h1 className="text-white text-base font-bold leading-none">Payments Console</h1>
                                <p className="text-emerald-400 text-[10px] uppercase tracking-widest font-semibold mt-1">Stripe + Credits</p>
                            </div>
                        </div>
                        <nav className="flex flex-col gap-1">
                            {navItems.map((item) => {
                                const isOverviewPricing = item.href.includes("/adminpayments");
                                const hasTab = item.href.includes("?tab=");
                                const currentSearch = typeof window !== "undefined" ? window.location.search : "";

                                const isActive = hasTab
                                    ? (pathname === "/adminpayments" && currentSearch.includes(item.href.split("?")[1]))
                                    : (pathname === item.href && (!isOverviewPricing || currentSearch === "" || currentSearch === "?"));

                                return (
                                    <Link
                                        key={item.label}
                                        href={item.href}
                                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive
                                            ? "bg-emerald-600 text-white shadow-lg"
                                            : "text-slate-400 hover:bg-slate-800 hover:text-white"
                                            }`}
                                    >
                                        <span className="material-symbols-outlined">
                                            {item.icon}
                                        </span>
                                        <p className="text-sm font-medium">{item.label}</p>
                                    </Link>
                                );
                            })}
                        </nav>
                    </div>
                    <div className="flex flex-col gap-4">
                        <div className="px-4 py-3 bg-slate-800 rounded-lg border border-slate-700">
                            <p className="text-xs text-slate-400 mb-1">Provider Cost Est.</p>
                            <p className="text-lg font-bold text-white">$ --.--</p>
                        </div>
                    </div>
                </aside>

                {/* Main Content Shell */}
                <main className="flex-1 flex flex-col overflow-y-auto w-full bg-slate-50 dark:bg-[#0f1117]">
                    {children}
                </main>
            </div>
        </ToastProvider>
    );
}
