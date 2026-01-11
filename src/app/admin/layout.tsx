"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const router = useRouter();
    const [adminName, setAdminName] = useState("Admin User");
    const [adminRole, setAdminRole] = useState("Super Admin");
    const [adminAvatar, setAdminAvatar] = useState("");
    const [isAuthorized, setIsAuthorized] = useState(false);

    useEffect(() => {
        const role = localStorage.getItem("user_role");
        const name = localStorage.getItem("user_name");
        const avatar = localStorage.getItem("user_avatar");

        if (role !== "admin") {
            router.push("/login");
        } else {
            setIsAuthorized(true);
            if (name) setAdminName(name);
            setAdminRole("Platform Administrator");
            if (avatar) setAdminAvatar(avatar);
        }
    }, [router]);

    if (!isAuthorized) return null;

    const navItems = [
        { label: "Overview", href: "/admin/dashboard", icon: "dashboard" },
        { label: "Users", href: "/admin/users", icon: "group" },
        { label: "Quotas", href: "/admin/quotas", icon: "speed" },
        { label: "Prompts", href: "/admin/prompts", icon: "terminal" },
        { label: "Performance", href: "/admin/performance", icon: "monitoring" },
    ];

    return (
        <div className="font-admin bg-[#0F172A] text-slate-200 min-h-screen flex overflow-hidden">
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 bg-[#0c1222] border-r border-slate-800 flex flex-col justify-between p-4">
                <div className="flex flex-col gap-8">
                    <div className="flex items-center gap-3 px-2">
                        <img src="/logo-dark.png" alt="uask.ai" className="h-8 w-auto" />
                        <div className="flex flex-col">
                            <h1 className="text-white text-base font-bold leading-none">uask.ai</h1>
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
                                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
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
                    <div className="flex items-center gap-3 px-2 py-2 border-t border-slate-800 pt-4">
                        <div className="size-8 rounded-full bg-slate-700 bg-cover bg-center overflow-hidden flex items-center justify-center border border-slate-700 shadow-sm">
                            {adminAvatar ? (
                                <img src={adminAvatar} alt={adminName} className="w-full h-full object-cover" />
                            ) : (
                                <span className="text-[10px] font-bold text-admin-primary">{adminName.split(' ').map(n => n[0]).join('')}</span>
                            )}
                        </div>
                        <div className="flex flex-col">
                            <p className="text-white text-xs font-bold truncate max-w-[120px]">{adminName}</p>
                            <p className="text-slate-500 text-[10px]">{adminRole}</p>
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
