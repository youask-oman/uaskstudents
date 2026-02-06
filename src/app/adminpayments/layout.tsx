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
        const role = localStorage.getItem("user_role") ?? "";
        const profile: AdminProfile = {
            name: localStorage.getItem("user_name") ?? "Admin User",
            role: role,
            avatar: localStorage.getItem("user_avatar") ?? "",
            authorized: role === "admin" || role === "devops",
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
        { label: "Requests Explorer", href: "/adminpayments?tab=requests", icon: "table_view" },
        { label: "Credit & Ledger", href: "/adminpayments?tab=credits", icon: "account_balance_wallet" },
        { label: "Pricing Config", href: "/adminpayments?tab=pricing", icon: "price_change" },
        { label: "Back to Main Admin", href: "/admin/dashboard", icon: "arrow_back" },
    ];

    return (
        <div
            suppressHydrationWarning
            className="font-admin bg-background-light text-slate-900 dark:bg-background-dark dark:text-slate-200 min-h-screen flex overflow-hidden transition-colors"
        >
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 bg-slate-900 text-white border-r border-slate-800 flex flex-col justify-between p-4 transition-colors">
                <div className="flex flex-col gap-8">
                    <div className="flex items-center gap-3 px-2">
                        <img src="/logo-dark.png" alt="uask.ai" className="h-8 w-auto invert brightness-0 grayscale-0" style={{ filter: "brightness(0) invert(1)" }} />
                        <div className="flex flex-col">
                            <h1 className="text-white text-base font-bold leading-none">Payments</h1>
                            <p className="text-emerald-400 text-[10px] uppercase tracking-widest font-semibold mt-1">Phase 0 Audit</p>
                        </div>
                    </div>
                    <nav className="flex flex-col gap-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.label}
                                href={item.href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${(pathname === item.href || (item.href.includes("?tab=") && pathname === "/adminpayments" && window.location.search.includes(item.href.split("?")[1])))
                                        ? "bg-emerald-600 text-white shadow-lg"
                                        : "text-slate-400 hover:bg-slate-800 hover:text-white"
                                    }`}
                            >
                                <span className="material-symbols-outlined">
                                    {item.icon}
                                </span>
                                <p className="text-sm font-medium">{item.label}</p>
                            </Link>
                        ))}
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
    );
}
