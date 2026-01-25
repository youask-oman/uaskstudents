"use client";

import { useMemo, useState, useEffect, useCallback } from "react";

interface UserListItem {
    id: number;
    full_name: string;
    email: string;
    subscription_tier: string;
    subscription_status?: string;
    plan_id?: number;
    plan_slug?: string;
    plan_name?: string;
    plan_credits_per_month?: number;
    plan_price_monthly_cents?: number;
    role: string;
    questions_count: number;
    scans_count: number;
    last_active_at: string;
}

const formatPlanName = (planName?: string, slug?: string, fallback?: string) => {
    if (planName) return planName;
    if (slug) {
        return slug
            .split(/[_\-]/)
            .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
            .join(" ");
    }
    if (fallback) return fallback;
    return "Unassigned";
};

const formatCurrencyFromCents = (cents?: number) => {
    if (cents === null || cents === undefined) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
};

const formatCreditLabel = (credits?: number) => {
    if (credits === null || credits === undefined) return "Credits TBD";
    return `${credits.toLocaleString()} credits / mo`;
};

export default function AdminUsersPage() {
    const [users, setUsers] = useState<UserListItem[]>([]);
    const [totalCount, setTotalCount] = useState(0);
    const [search, setSearch] = useState("");
    const [roleFilter, setRoleFilter] = useState("");
    const [planFilter, setPlanFilter] = useState("");
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [limit] = useState(10);
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [inviteForm, setInviteForm] = useState({ full_name: "", email: "", password: "TempPassword123!", academic_level: "High School" });
    const [activeRowMenu, setActiveRowMenu] = useState<number | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [availablePlans, setAvailablePlans] = useState<{ id: number; name: string; slug: string }[]>([]);
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    const getAuthHeaders = (includeJson = false) => {
        const token = localStorage.getItem("token");
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) {
            (headers as Record<string, string>)["Content-Type"] = "application/json";
        }
        return headers;
    };

    const fetchUsers = useCallback(async (pageToFetch: number, signal?: AbortSignal) => {
        setLoading(true);
        try {
            setErrorMessage(null);
            const params = new URLSearchParams();
            if (search) params.append("q", search);
            if (roleFilter) params.append("role", roleFilter);
            if (planFilter) params.append("plan", planFilter);
            params.append("offset", ((pageToFetch - 1) * limit).toString());
            params.append("limit", limit.toString());

            const res = await fetch(`${baseUrl}/api/v1/admin/users?${params.toString()}`, {
                headers: getAuthHeaders(),
                signal
            });
            if (!res.ok) {
                throw new Error("Failed to load user list.");
            }
            const data = await res.json();
            setUsers(data.users);
            setTotalCount(data.total_count);
        } catch (error) {
            if ((error as Error).name === "AbortError") return;
            console.error("Failed to load user list", error);
            setErrorMessage("Unable to load users. Please refresh.");
        } finally {
            setLoading(false);
        }
    }, [baseUrl, limit, search, roleFilter, planFilter]);

    useEffect(() => {
        const controller = new AbortController();
        fetchUsers(page, controller.signal);
        return () => controller.abort();
    }, [fetchUsers, page]);

    const roleOptions = useMemo(() => {
        const roles = new Set<string>();
        users.forEach((user) => {
            if (user.role) roles.add(user.role.toLowerCase());
        });
        return Array.from(roles).sort();
    }, [users]);

    useEffect(() => {
        const controller = new AbortController();
        const loadPlans = async () => {
            try {
                const res = await fetch(`${baseUrl}/api/v1/admin/plans`, { headers: getAuthHeaders(), signal: controller.signal });
                if (res.ok) {
                    const data = await res.json();
                    setAvailablePlans(Array.isArray(data) ? data : []);
                }
            } catch (error) {
                if ((error as Error).name === "AbortError") return;
                console.error("Failed to load plans", error);
            }
        };
        loadPlans();
        return () => controller.abort();
    }, [baseUrl]);

    const handleInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/invite`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify(inviteForm),
            });
            if (res.ok) {
                setShowInviteModal(false);
                fetchUsers(page);
            } else {
                throw new Error("Invite failed.");
            }
        } catch (error) {
            console.error("Invite failed:", error);
            setErrorMessage("Unable to send invite. Please retry.");
        }
    };

    const exportToCSV = () => {
    const headers = ["ID", "Name", "Email", "Plan", "Role", "Questions", "Scans", "Last Active"];
    const rows = users.map(u => [
        u.id,
        u.full_name,
        u.email,
        formatPlanName(u.plan_name, u.plan_slug, u.subscription_tier),
        u.role,
        u.questions_count,
        u.scans_count,
        u.last_active_at
    ]);
        const csvContent = "data:text/csv;charset=utf-8," + [headers, ...rows].map(e => e.join(",")).join("\n");
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "uask_users.csv");
        document.body.appendChild(link);
        link.click();
    };

    const updateRole = async (userId: number, newRole: string) => {
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${userId}`, {
                method: "PATCH",
                headers: getAuthHeaders(true),
                body: JSON.stringify({ role: newRole.toLowerCase() }),
            });
            if (res.ok) fetchUsers(page);
            else throw new Error("Role update failed.");
        } catch (error) {
            console.error("Role update failed:", error);
            setErrorMessage("Unable to update role.");
        }
    };

    const performAction = async (userId: number, action: string) => {
        setActiveRowMenu(null);
        try {
            let res;
            setErrorMessage(null);
            if (action === "reset") res = await fetch(`${baseUrl}/api/v1/admin/users/${userId}/reset-password`, { method: "POST", headers: getAuthHeaders() });
            if (action === "ban") res = await fetch(`${baseUrl}/api/v1/admin/users/${userId}/ban`, { method: "PATCH", headers: getAuthHeaders() });
            if (action === "delete") {
                if (!confirm("Are you sure you want to delete this user?")) return;
                res = await fetch(`${baseUrl}/api/v1/admin/users/${userId}`, { method: "DELETE", headers: getAuthHeaders() });
            }
            if (res?.ok) fetchUsers(page);
            else if (res) throw new Error("Action failed.");
        } catch (error) {
            console.error("Action failed:", error);
            setErrorMessage("Unable to complete admin action.");
        }
    };

    return (
        <div className="flex flex-col flex-1 p-8 gap-8">
            <div className="flex flex-col gap-6">
                <div className="flex justify-between items-end">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white tracking-tight">User Directory</h1>
                        <p className="text-slate-400 text-sm mt-1">Manage platform access, roles, and subscription status.</p>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => setShowInviteModal(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-lg shadow-lg shadow-primary/20 transition-all">
                            <span className="material-symbols-outlined text-[18px]">person_add</span>
                            Invite User
                        </button>
                        <button
                            onClick={exportToCSV}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-lg border border-slate-700 transition-all">
                            <span className="material-symbols-outlined text-[18px]">download</span>
                            Export CSV
                        </button>
                    </div>
                </div>
                {errorMessage && (
                    <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs font-bold uppercase tracking-widest text-rose-300">
                        {errorMessage}
                    </div>
                )}

                <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-4 rounded-xl flex items-center justify-between gap-4">
                    <div className="flex-1 flex items-center gap-4">
                        <div className="relative flex-1 max-w-md">
                            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-[20px]">search</span>
                            <input
                                className="w-full bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-500 focus:ring-admin-primary focus:border-admin-primary"
                                placeholder="Search students or staff (Name, Email)..."
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                            />
                        </div>
                        <div className="h-8 w-px bg-slate-800"></div>
                        <div className="flex gap-3">
                            <select
                                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-900 dark:text-white px-3 py-2 focus:ring-admin-primary"
                                value={roleFilter}
                                onChange={(e) => setRoleFilter(e.target.value)}
                            >
                                <option value="">All Roles</option>
                                {roleOptions.map((role) => (
                                    <option key={role} value={role}>
                                        {role.charAt(0).toUpperCase() + role.slice(1)}
                                    </option>
                                ))}
                            </select>
                            <select
                                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-medium text-slate-900 dark:text-white px-3 py-2 focus:ring-admin-primary"
                                value={planFilter}
                                onChange={(e) => setPlanFilter(e.target.value)}
                            >
                                <option value="">All Plans</option>
                                {availablePlans.map((plan) => (
                                    <option key={plan.slug} value={plan.slug}>
                                        {plan.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 font-medium">Showing {users.length} of {totalCount} users</span>
                    </div>
                </div>
            </div>

            <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xl">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">User Information</th>
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Plan</th>
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Usage (Q / OCR)</th>
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Role</th>
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Last Active</th>
                            <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                                    <div className="flex justify-center items-center gap-3">
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-admin-primary"></div>
                                        <span>Syncing user records...</span>
                                    </div>
                                </td>
                            </tr>
                        ) : users.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-6 py-8 text-center text-slate-500 italic">No users found matching your filters.</td>
                            </tr>
                        ) : (
                            users.map((user) => (
                                <tr key={user.id} className="hover:bg-admin-primary/[0.05] transition-colors cursor-pointer group">
                                    <td className="px-6 py-4" onClick={() => window.location.href = `/admin/users/${user.id}`}>
                                        <div className="flex items-center gap-3">
                                            <div className="h-10 w-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-admin-primary font-bold border border-slate-200 dark:border-slate-700">
                                                {user.full_name.split(' ').map(n => n[0]).join('')}
                                            </div>
                                            <div className="flex flex-col">
                                                <span className="text-sm font-bold text-slate-900 dark:text-white group-hover:text-admin-primary transition-colors">{user.full_name}</span>
                                                <span className="text-xs text-slate-500">{user.email}</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-sm font-bold text-slate-900 dark:text-white">
                                                {formatPlanName(user.plan_name, user.plan_slug, user.subscription_tier)}
                                            </span>
                                            <span className="text-[10px] uppercase tracking-[0.3em] text-slate-500">
                                                {user.plan_slug ? user.plan_slug.replace(/_/g, " ").toUpperCase() : user.subscription_tier.toUpperCase()}
                                            </span>
                                            <span className="text-[11px] text-slate-400">
                                                {formatCreditLabel(user.plan_credits_per_month)}
                                            </span>
                                            <span className="text-[11px] text-slate-400">
                                                {formatCurrencyFromCents(user.plan_price_monthly_cents)} / mo
                                            </span>
                                            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest font-semibold text-slate-500">
                                                <span className="size-1 rounded-full bg-slate-500"></span>
                                                {user.subscription_status ? user.subscription_status.replace(/_/g, " ").toUpperCase() : "UNKNOWN STATUS"}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex flex-col gap-1">
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-white font-medium">{user.questions_count}</span>
                                                <span className="text-[10px] text-slate-500">questions</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-white font-medium">{user.scans_count}</span>
                                                <span className="text-[10px] text-slate-500">OCR scans</span>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <select
                                            value={user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                                            onChange={(e) => updateRole(user.id, e.target.value)}
                                            className={`flex items-center gap-2 px-2 py-1 rounded text-xs font-bold border outline-none cursor-pointer ${user.role === 'admin'
                                                ? 'bg-admin-primary/20 text-admin-primary border-admin-primary/30'
                                                : user.role === 'supervisor'
                                                    ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30'
                                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                                                }`}>
                                            <option value="Student">Student</option>
                                            <option value="Supervisor">Supervisor</option>
                                            <option value="Admin">Admin</option>
                                        </select>
                                    </td>
                                    <td className="px-6 py-4 text-xs text-slate-400">
                                        {new Date(user.last_active_at).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4 text-right relative">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); setActiveRowMenu(activeRowMenu === user.id ? null : user.id); }}
                                            className="text-slate-400 hover:text-white px-2 py-1">
                                            <span className="material-symbols-outlined text-[20px]">more_vert</span>
                                        </button>
                                        {activeRowMenu === user.id && (
                                            <div className="absolute right-6 top-10 w-40 bg-slate-900 border border-slate-800 rounded-lg shadow-2xl z-20 overflow-hidden">
                                                <button onClick={() => performAction(user.id, "reset")} className="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-slate-800 flex items-center gap-2">
                                                    <span className="material-symbols-outlined text-sm">lock_reset</span> Reset Password
                                                </button>
                                                <button onClick={() => performAction(user.id, "ban")} className="w-full px-4 py-2 text-left text-xs font-bold text-rose-500 hover:bg-slate-800 flex items-center gap-2">
                                                    <span className="material-symbols-outlined text-sm">block</span> Ban Account
                                                </button>
                                                <button onClick={() => performAction(user.id, "delete")} className="w-full px-4 py-2 text-left text-xs font-bold text-rose-600 hover:bg-slate-800 flex items-center gap-2">
                                                    <span className="material-symbols-outlined text-sm">delete</span> Delete User
                                                </button>
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
                <div className="px-6 py-4 bg-slate-50 dark:bg-slate-900/30 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <p className="text-[11px] text-slate-500 font-medium">Showing <span className="text-slate-300">{(page - 1) * limit + 1}-{Math.min(page * limit, totalCount)}</span> of <span className="text-slate-300">{totalCount}</span> users</p>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white disabled:opacity-50">
                            <span className="material-symbols-outlined text-[20px]">chevron_left</span>
                        </button>
                        <button
                            disabled={page * limit >= totalCount}
                            onClick={() => setPage(p => p + 1)}
                            className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white disabled:opacity-50">
                            <span className="material-symbols-outlined text-[20px]">chevron_right</span>
                        </button>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-5 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 bg-slate-800 rounded-lg">
                            <span className="material-symbols-outlined text-slate-400">group</span>
                        </div>
                    <h3 className="font-bold text-slate-900 dark:text-white text-sm">Students</h3>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed mb-4">Default role. Access to question solving, OCR scans, and study materials based on their subscription tier.</p>
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">User Level Access</div>
                </div>
                <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-5 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                            <span className="material-symbols-outlined">verified</span>
                        </div>
                    <h3 className="font-bold text-slate-900 dark:text-white text-sm">Supervisors</h3>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed mb-4">Manage group quotas, view organization activity logs, and moderate community threads.</p>
                    <div className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">Moderator Level</div>
                </div>
                <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-5 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 bg-admin-primary/10 rounded-lg text-admin-primary">
                            <span className="material-symbols-outlined">admin_panel_settings</span>
                        </div>
                    <h3 className="font-bold text-slate-900 dark:text-white text-sm">Admins</h3>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed mb-4">Full system access. Assign roles, manage system configuration, and handle billing exceptions.</p>
                    <div className="text-[10px] font-bold text-admin-primary uppercase tracking-widest">Full System Access</div>
                </div>
            </div>

            <footer className="mt-auto py-6 text-center border-t border-slate-200 dark:border-slate-800">
                <p className="text-[11px] text-slate-600 font-medium uppercase tracking-widest">uask.ai Administrative Engine • Directory v4.2.0 • Build 2024.11.05</p>
            </footer>

            {showInviteModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-md p-8 shadow-2xl">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Invite New User</h2>
                            <button onClick={() => setShowInviteModal(false)} className="text-slate-500 hover:text-white">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                        <form onSubmit={handleInvite} className="space-y-4">
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-400 uppercase">Full Name</label>
                                <input
                                    required
                                    className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                    placeholder="Jane Doe"
                                    value={inviteForm.full_name}
                                    onChange={e => setInviteForm({ ...inviteForm, full_name: e.target.value })}
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-400 uppercase">Email Address</label>
                                <input
                                    required
                                    type="email"
                                    className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                    placeholder="jane@uask.ai"
                                    value={inviteForm.email}
                                    onChange={e => setInviteForm({ ...inviteForm, email: e.target.value })}
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="text-xs font-bold text-slate-400 uppercase">Temp Password</label>
                                    <input
                                        required
                                    className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                        value={inviteForm.password}
                                        onChange={e => setInviteForm({ ...inviteForm, password: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-xs font-bold text-slate-400 uppercase">Level</label>
                                    <select
                                    className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                        value={inviteForm.academic_level}
                                        onChange={e => setInviteForm({ ...inviteForm, academic_level: e.target.value })}
                                    >
                                        <option>High School</option>
                                        <option>Undergraduate</option>
                                        <option>Graduate</option>
                                    </select>
                                </div>
                            </div>
                            <button type="submit" className="w-full bg-admin-primary hover:bg-blue-600 text-white font-bold py-3 rounded-xl shadow-lg shadow-admin-primary/20 transition-all mt-4">
                                Send Invitation
                            </button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
