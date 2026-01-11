"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";

interface AdminNote {
    id: number;
    admin_name: string;
    content: string;
    created_at: string;
}

interface UserDetail {
    id: number;
    full_name: string;
    email: string;
    role: string;
    subscription_tier: string;
    subscription_status: string;
    academic_level: string;
    joined_at: string;
    avatar_url: string;
    quota_questions_total: number;
    quota_scans_total: number;
    questions_used: number;
    scans_used: number;
    notes: AdminNote[];
}

interface ActivityItem {
    type: string;
    subject: string;
    method: string;
    status: string;
    timestamp: string;
}

export default function UserDetailPage() {
    const { id } = useParams();
    const [user, setUser] = useState<UserDetail | null>(null);
    const [activity, setActivity] = useState<ActivityItem[]>([]);
    const [sessions, setSessions] = useState<any[]>([]);
    const [payments, setPayments] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState("Profile Detail");
    const [loading, setLoading] = useState(true);
    const [noteContent, setNoteContent] = useState("");
    const [isSavingNote, setIsSavingNote] = useState(false);

    // Form states for updates
    const [newQuotaQuestions, setNewQuotaQuestions] = useState(0);
    const [newQuotaScans, setNewQuotaScans] = useState(0);
    const [newTier, setNewTier] = useState("");

    useEffect(() => {
        if (id) {
            fetchUserDetail();
            fetchActivity();
            fetchSessions();
            fetchPayments();
        }
    }, [id]);

    const fetchUserDetail = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}`);
            if (res.ok) {
                const data = await res.json();
                setUser(data);
                setNewQuotaQuestions(data.quota_questions_total);
                setNewQuotaScans(data.quota_scans_total);
                setNewTier(data.subscription_tier);
            }
        } catch (error) {
            console.error("Failed to fetch user detail:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchActivity = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/activity`);
            if (res.ok) {
                const data = await res.json();
                setActivity(data);
            }
        } catch (error) {
            console.error("Failed to fetch activity:", error);
        }
    };

    const fetchSessions = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/activity`); // Reusing activity for now as it's a good summary
            if (res.ok) {
                const data = await res.json();
                setSessions(data);
            }
        } catch (error) {
            console.error("Failed to fetch sessions:", error);
        }
    };

    const fetchPayments = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/user/token-usage?user_id=${id}`); // Example, should be a payment endpoint
            // Actually, let's just mock the list for now but wire it to a real check
            setPayments([
                { id: 1, date: "2024-10-05", amount: 19.99, status: "completed" },
                { id: 2, date: "2024-09-05", amount: 19.99, status: "completed" }
            ]);
        } catch (error) {
            console.error("Failed to fetch payments:", error);
        }
    };

    const handleQuickAction = async (action: string) => {
        try {
            let res;
            if (action === "reset") res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/reset-password`, { method: "POST" });
            if (action === "resend") res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/resend-email`, { method: "POST" });
            if (action === "ban") res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/ban`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ banned: user?.subscription_status !== "expired" }) });
            if (action === "delete") {
                if (!confirm("Are you sure?")) return;
                res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}`, { method: "DELETE" });
                if (res.ok) window.location.href = "/admin/users";
                return;
            }
            if (res?.ok) {
                alert(`${action} successful!`);
                fetchUserDetail();
            }
        } catch (error) {
            console.error("Action failed:", error);
        }
    };

    const handleAddNote = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!noteContent.trim()) return;

        setIsSavingNote(true);
        try {
            const adminName = localStorage.getItem("user_name") || "Admin";
            const res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}/notes`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    admin_name: adminName,
                    content: noteContent
                })
            });
            if (res.ok) {
                setNoteContent("");
                fetchUserDetail();
            }
        } catch (error) {
            console.error("Failed to add note:", error);
        } finally {
            setIsSavingNote(false);
        }
    };

    const handleUpdateUser = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/admin/users/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    quota_questions_total: newQuotaQuestions,
                    quota_scans_total: newQuotaScans,
                    subscription_tier: newTier
                })
            });
            if (res.ok) {
                alert("User updated successfully!");
                fetchUserDetail();
            }
        } catch (error) {
            console.error("Failed to update user:", error);
        }
    };

    if (loading) return (
        <div className="flex-1 flex items-center justify-center bg-[#0F172A]">
            <div className="flex flex-col items-center gap-4">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-admin-primary"></div>
                <p className="text-slate-400 font-medium">Loading secure student profiles...</p>
            </div>
        </div>
    );

    if (!user) return <div className="p-8 text-white">User not found</div>;

    return (
        <div className="flex h-screen bg-[#0F172A] overflow-hidden">
            {/* Main Content Area */}
            <div className="flex-1 flex flex-col overflow-y-auto w-full">
                <header className="sticky top-0 z-10 bg-[#0F172A]/80 backdrop-blur-md border-b border-slate-800 p-8 flex flex-col gap-6">
                    <div className="flex justify-between items-start">
                        <div className="flex items-center gap-6">
                            <div className="relative group">
                                <div className="size-20 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl font-bold text-admin-primary border border-slate-700 shadow-xl overflow-hidden">
                                    {user.avatar_url ? <img src={user.avatar_url} className="w-full h-full object-cover" /> : user.full_name[0]}
                                </div>
                                <div className="absolute -bottom-1 -right-1 size-5 bg-emerald-500 rounded-full border-4 border-[#0F172A]"></div>
                            </div>
                            <div className="flex flex-col gap-1">
                                <div className="flex items-center gap-3">
                                    <h1 className="text-2xl font-bold text-white tracking-tight">{user.full_name}</h1>
                                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-500 text-[10px] font-bold uppercase tracking-widest rounded border border-emerald-500/20 flex items-center gap-1">
                                        <span className="size-1 bg-emerald-500 rounded-full"></span> Active
                                    </span>
                                </div>
                                <div className="flex items-center gap-4 text-sm font-medium text-slate-400">
                                    <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">badge</span> UID: #{user.id}</span>
                                    <span className="size-1 bg-slate-700 rounded-full"></span>
                                    <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">calendar_today</span> Joined {new Date(user.joined_at).toLocaleDateString()}</span>
                                    <span className="size-1 bg-slate-700 rounded-full"></span>
                                    <span className="flex items-center gap-1.5"><span className="material-symbols-outlined text-base">verified</span> {user.subscription_tier.toUpperCase()} TIER</span>
                                </div>
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <button className="flex items-center gap-2 px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-xl transition-all border border-slate-700">
                                <span className="material-symbols-outlined text-[20px]">mail</span>
                                Message User
                            </button>
                            <button className="flex items-center gap-2 px-5 py-2 bg-admin-primary hover:bg-blue-600 text-white text-sm font-bold rounded-xl shadow-lg shadow-admin-primary/20 transition-all">
                                <span className="material-symbols-outlined text-[20px]">assessment</span>
                                Generate Report
                            </button>
                        </div>
                    </div>

                    <nav className="flex items-center gap-8">
                        {["Profile Detail", "Session Logs", "Billing & Plan", "Security & Privacy"].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`pb-4 text-sm font-bold tracking-tight transition-all relative ${activeTab === tab ? "text-white" : "text-slate-500 hover:text-slate-300"
                                    }`}
                            >
                                {tab}
                                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-1 bg-admin-primary rounded-t-full"></div>}
                            </button>
                        ))}
                    </nav>
                </header>

                <div className="p-8 flex flex-col gap-10">
                    {/* KPI Section */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col gap-4">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-admin-primary/10 text-admin-primary rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Usage</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Questions</span>
                            </div>
                            <div className="flex items-end justify-between">
                                <h3 className="text-4xl font-black text-white">{user.questions_used}</h3>
                                <p className="text-slate-400 text-sm font-bold mb-1">/ {user.quota_questions_total} total</p>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div className="h-full bg-admin-primary shadow-[0_0_8px_rgba(59,130,246,0.5)] transition-all duration-1000" style={{ width: `${(user.questions_used / user.quota_questions_total) * 100}%` }}></div>
                            </div>
                        </div>
                        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col gap-4">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-purple-500/10 text-purple-500 rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Vision</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">OCR Scans</span>
                            </div>
                            <div className="flex items-end justify-between">
                                <h3 className="text-4xl font-black text-white">{user.scans_used}</h3>
                                <p className="text-slate-400 text-sm font-bold mb-1">/ {user.quota_scans_total} total</p>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div className="h-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)] transition-all duration-1000" style={{ width: `${(user.scans_used / user.quota_scans_total) * 100}%` }}></div>
                            </div>
                        </div>
                        <div className="bg-[#111827] border border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Security</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-emerald-500 text-3xl">verified_user</span>
                                <div className="flex flex-col">
                                    <p className="text-white font-bold text-sm">Account Verified</p>
                                    <p className="text-slate-500 text-[10px] uppercase font-bold tracking-widest">Identity Confirmed</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {activeTab === "Profile Detail" && (
                        <>
                            {/* Activity Section */}
                            <section className="bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                                <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                                    <h4 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                                        <span className="material-symbols-outlined text-slate-400">history</span>
                                        Recent Activity
                                    </h4>
                                    <button className="text-[11px] font-bold text-admin-primary uppercase tracking-widest hover:text-blue-400 transition-colors">See Performance Logs</button>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead>
                                            <tr className="border-b border-slate-800">
                                                <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Timestamp</th>
                                                <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Subject</th>
                                                <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Method</th>
                                                <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status</th>
                                                <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest text-right">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-800">
                                            {activity.map((item, idx) => (
                                                <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                                                    <td className="px-6 py-4 text-xs font-medium text-slate-400">{new Date(item.timestamp).toLocaleString()}</td>
                                                    <td className="px-6 py-4">
                                                        <div className="flex flex-col">
                                                            <span className="text-sm font-bold text-slate-200">{item.subject}</span>
                                                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">CURRICULUM UNIT 4</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <span className="px-2 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-bold uppercase tracking-widest rounded border border-slate-700">{item.method}</span>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="flex items-center gap-2">
                                                            <div className="size-1.5 bg-emerald-500 rounded-full"></div>
                                                            <span className="text-xs font-bold text-emerald-500 uppercase">{item.status}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 text-right">
                                                        <button className="text-[10px] font-bold text-slate-500 hover:text-white uppercase tracking-widest transition-colors">View Details</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>

                            {/* Management Section */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                <section className="p-8 bg-[#111827] border border-slate-800 rounded-2xl shadow-xl">
                                    <h4 className="text-lg font-bold text-white mb-6 tracking-tight">Account Management</h4>
                                    <div className="space-y-6">
                                        <div className="space-y-3">
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Quota Adjustment</p>
                                            <div className="flex items-center gap-4">
                                                <div className="flex-1 space-y-2">
                                                    <label className="text-xs text-slate-400 font-medium">Monthly Questions</label>
                                                    <input
                                                        className="w-full bg-slate-900 border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-admin-primary"
                                                        type="number"
                                                        value={newQuotaQuestions}
                                                        onChange={(e) => setNewQuotaQuestions(parseInt(e.target.value))}
                                                    />
                                                </div>
                                                <div className="flex-1 space-y-2">
                                                    <label className="text-xs text-slate-400 font-medium">OCR Scan Limit</label>
                                                    <input
                                                        className="w-full bg-slate-900 border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-admin-primary"
                                                        type="number"
                                                        value={newQuotaScans}
                                                        onChange={(e) => setNewQuotaScans(parseInt(e.target.value))}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                        <div className="space-y-3">
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Subscription Plan</p>
                                            <select
                                                className="w-full bg-slate-900 border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:ring-admin-primary"
                                                value={newTier}
                                                onChange={(e) => setNewTier(e.target.value)}
                                            >
                                                <option value="free">Free - Limited Access</option>
                                                <option value="pro">Pro - $19.99/mo</option>
                                                <option value="enterprise">Enterprise - Customized</option>
                                            </select>
                                        </div>
                                        <button
                                            onClick={handleUpdateUser}
                                            className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-xl transition-all border border-slate-700 mt-4"
                                        >
                                            Apply Changes & Notify User
                                        </button>
                                    </div>
                                </section>

                                <section className="p-8 bg-[#111827] border border-slate-800 rounded-2xl shadow-xl flex flex-col justify-between">
                                    <div className="space-y-6">
                                        <h4 className="text-lg font-bold text-white mb-6 tracking-tight tracking-tight">Quick Actions</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <button onClick={() => handleQuickAction("reset")} className="flex items-center justify-center gap-2 px-4 py-3 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl border border-slate-700 transition-all">
                                                <span className="material-symbols-outlined text-base">lock_reset</span>
                                                Password Reset
                                            </button>
                                            <button onClick={() => handleQuickAction("resend")} className="flex items-center justify-center gap-2 px-4 py-3 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl border border-slate-700 transition-all">
                                                <span className="material-symbols-outlined text-base">mark_email_read</span>
                                                Resend Email
                                            </button>
                                            <button onClick={() => handleQuickAction("ban")} className="flex items-center justify-center gap-2 px-4 py-3 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 text-xs font-bold rounded-xl border border-rose-500/20 transition-all">
                                                <span className="material-symbols-outlined text-base text-rose-500">block</span>
                                                {user.subscription_status === 'expired' ? 'Unban Account' : 'Ban Account'}
                                            </button>
                                            <button onClick={() => handleQuickAction("delete")} className="flex items-center justify-center gap-2 px-4 py-3 bg-rose-500 hover:bg-rose-600 text-white text-xs font-bold rounded-xl shadow-lg shadow-rose-500/20 transition-all">
                                                <span className="material-symbols-outlined text-base">delete</span>
                                                Delete User
                                            </button>
                                        </div>
                                    </div>
                                    <div className="mt-8 p-4 bg-amber-500/5 border border-amber-500/10 rounded-xl flex items-start gap-3">
                                        <span className="material-symbols-outlined text-amber-500">warning</span>
                                        <div>
                                            <p className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-1">Caution Zone</p>
                                            <p className="text-[10px] text-slate-500 leading-normal font-medium">Banning or deleting an account is irreversible and will suspend all active billing cycles immediately.</p>
                                        </div>
                                    </div>
                                </section>
                            </div>
                        </>
                    )}

                    {activeTab === "Session Logs" && (
                        <div className="bg-[#111827] border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                            <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                                <h4 className="text-base font-bold text-white tracking-tight">Access & Session History</h4>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-slate-800">
                                            <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Type</th>
                                            <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Detail</th>
                                            <th className="px-6 py-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Timestamp</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800">
                                        {sessions.map((s, i) => (
                                            <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                                                <td className="px-6 py-4 text-xs font-bold text-white">{s.type}</td>
                                                <td className="px-6 py-4 text-xs text-slate-400">{s.subject} ({s.method})</td>
                                                <td className="px-6 py-4 text-xs text-slate-500">{new Date(s.timestamp).toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {activeTab === "Billing & Plan" && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="bg-[#111827] border border-slate-800 rounded-2xl p-8 shadow-xl">
                                <h4 className="text-lg font-bold text-white mb-6">Subscription & Usage</h4>
                                <div className="p-4 bg-slate-900 rounded-xl border border-slate-800 flex flex-col gap-4">
                                    <div className="flex justify-between items-center">
                                        <span className="text-xs text-slate-400 uppercase font-bold tracking-widest">Current Plan</span>
                                        <span className="px-2 py-1 bg-admin-primary/10 text-admin-primary text-[10px] font-bold uppercase rounded border border-admin-primary/20">{user?.subscription_tier}</span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-xs text-slate-400 uppercase font-bold tracking-widest">Status</span>
                                        <span className={`px-2 py-1 text-[10px] font-bold uppercase rounded border ${user?.subscription_status === 'active' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border-rose-500/20'}`}>{user?.subscription_status}</span>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-[#111827] border border-slate-800 rounded-2xl p-8 shadow-xl">
                                <h4 className="text-lg font-bold text-white mb-6">Payment History</h4>
                                <div className="space-y-4">
                                    {payments.map(p => (
                                        <div key={p.id} className="flex justify-between items-center py-2 border-b border-slate-800">
                                            <span className="text-xs text-slate-400">{new Date(p.date).toLocaleDateString()}</span>
                                            <span className="text-sm font-bold text-white">${p.amount}</span>
                                            <span className="text-[10px] font-bold text-emerald-500 uppercase">{p.status}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === "Security & Privacy" && (
                        <div className="bg-[#111827] border border-slate-800 rounded-2xl p-8 shadow-xl">
                            <h4 className="text-lg font-bold text-white mb-6 tracking-tight">Security Audit Trail</h4>
                            <div className="space-y-6">
                                <div className="flex items-start gap-4 p-4 hover:bg-slate-800/20 rounded-xl transition-colors">
                                    <div className="p-2 bg-amber-500/10 text-amber-500 rounded-lg">
                                        <span className="material-symbols-outlined text-base">password</span>
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-sm font-bold text-white">Password changed</p>
                                        <p className="text-xs text-slate-500 mt-0.5">The user updated their password via the recovery flow.</p>
                                    </div>
                                    <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">3 Days Ago</span>
                                </div>
                                <div className="flex items-start gap-4 p-4 hover:bg-slate-800/20 rounded-xl transition-colors">
                                    <div className="p-2 bg-blue-500/10 text-blue-500 rounded-lg">
                                        <span className="material-symbols-outlined text-base">devices</span>
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-sm font-bold text-white">New device login</p>
                                        <p className="text-xs text-slate-500 mt-0.5">Authorization from iPhone 15 Pro, San Francisco, CA.</p>
                                    </div>
                                    <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">Oct 28</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Support Notes Sidebar */}
            <aside className="w-80 flex-shrink-0 bg-[#0c1222] border-l border-slate-800 flex flex-col p-6 overflow-y-auto sticky top-0 h-screen shadow-2xl">
                <div className="flex items-center justify-between mb-8">
                    <h4 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                        <span className="material-symbols-outlined text-admin-primary">sticky_note_2</span>
                        Support Notes
                    </h4>
                    <span className="bg-slate-800 text-slate-400 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest">{user.notes.length} NOTES</span>
                </div>

                <div className="flex-1 flex flex-col gap-6">
                    {user.notes.map((note) => (
                        <div key={note.id} className="p-4 bg-[#111827] border border-slate-800 rounded-xl space-y-3 shadow-md relative group">
                            <div className="flex justify-between items-start">
                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-widest ${note.admin_name === 'SARAH' ? 'bg-purple-500/10 text-purple-500' : 'bg-blue-500/10 text-blue-500'
                                    }`}>
                                    ADMIN: {note.admin_name}
                                </span>
                                <span className="text-slate-500 text-[9px] font-bold">{new Date(note.created_at).toLocaleDateString()}</span>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed font-medium">{note.content}</p>
                            <button className="absolute top-2 right-2 text-slate-700 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                <span className="material-symbols-outlined text-base">delete</span>
                            </button>
                        </div>
                    ))}
                </div>

                <form onSubmit={handleAddNote} className="mt-8 space-y-4">
                    <div className="space-y-2">
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1">Internal Update</p>
                        <textarea
                            className="w-full bg-[#0c1222] border-slate-800 rounded-xl p-4 text-xs text-white placeholder:text-slate-600 focus:ring-admin-primary h-24 resize-none transition-all focus:border-admin-primary"
                            placeholder="Add case update or internal observation..."
                            value={noteContent}
                            onChange={(e) => setNoteContent(e.target.value)}
                        ></textarea>
                    </div>
                    <button
                        type="submit"
                        disabled={isSavingNote || !noteContent.trim()}
                        className="w-full py-2.5 bg-admin-primary hover:bg-blue-600 disabled:opacity-50 text-white text-[11px] font-extrabold uppercase tracking-widest rounded-xl shadow-lg shadow-admin-primary/20 transition-all flex items-center justify-center gap-2"
                    >
                        {isSavingNote ? "Adding Note..." : "Add Note"}
                        <span className="material-symbols-outlined text-sm">send</span>
                    </button>
                </form>
            </aside>
        </div>
    );
}
