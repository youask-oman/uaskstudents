"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import navManifest from "../../../admin_nav_manifest.json";
import { ToastProvider } from "@/components/ui/ToastProvider";

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
            authorized: role === "admin" || role === "superadmin",
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

    const adminRoleLabel = adminProfile.role === "superadmin" ? "Super Admin" : "Platform Administrator";

    const navItems = Array.isArray(navManifest?.nav_items) ? navManifest.nav_items : [];


    return (
        <ToastProvider>
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
                            {navItems.map((item, index) => {
                                if (item.type === "divider") {
                                    return (
                                        <div
                                            key={`divider-${index}`}
                                            className="my-3 h-px w-full bg-slate-200 dark:bg-slate-800"
                                        />
                                    );
                                }
                                return (
                                    <Link
                                        key={`${item.href}-${index}`}
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
                                );
                            })}
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
        </ToastProvider>
    );
}
