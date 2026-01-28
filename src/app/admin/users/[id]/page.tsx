"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Image from "next/image";

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
    subscription_id?: number;
    plan_id?: number;
    plan_slug?: string;
    plan_name?: string;
    plan_credits_per_month?: number;
    plan_price_monthly_cents?: number;
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

type GenericRecord = Record<string, unknown>;

interface FullUserData {
    user: GenericRecord;
    subscription: GenericRecord;
    plan: GenericRecord;
    usage_ledger: GenericRecord[];
    usage_logs: GenericRecord[];
    payments: GenericRecord[];
    quota_overrides: GenericRecord[];
    admin_notes: GenericRecord[];
    sessions: GenericRecord[];
    messages: GenericRecord[];
    uploads: GenericRecord[];
    crops: GenericRecord[];
    ocr_jobs: GenericRecord[];
    ocr_artifacts: GenericRecord[];
    ocr_questions: GenericRecord[];
    ocr_choices: GenericRecord[];
    ocr_figures: GenericRecord[];
    ocr_confirmations: GenericRecord[];
    ocr_audit_events: GenericRecord[];
    voice_sessions: GenericRecord[];
    voice_audios: GenericRecord[];
    voice_jobs: GenericRecord[];
    voice_artifacts: GenericRecord[];
    voice_confirmations: GenericRecord[];
    saved_solutions: GenericRecord[];
    request_events: GenericRecord[];
    device_signup_logs: GenericRecord[];
}

const formatDateTime = (value: unknown) => {
    if (!value) return "n/a";
    const date = new Date(value as string | number | Date);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
};

const renderFieldValue = (value: unknown) => {
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
};

const renderShortText = (value: unknown, maxLength = 240) => {
    const text = renderFieldValue(value);
    if (text === "n/a") return text;
    if (text.length <= maxLength) return text;
    return `${text.slice(0, maxLength)}...`;
};

const formatPlanName = (planName?: string, slug?: string, fallback?: string) => {
    if (planName) return planName;
    if (slug) {
        return slug
            .split(/[_\-]/)
            .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
            .join(" ");
    }
    if (fallback) return fallback;
    return "Unassigned Plan";
};

const formatCurrencyFromCents = (cents?: number) => {
    if (cents === null || cents === undefined) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
};

const formatCreditsLabel = (credits?: number) => {
    if (credits === null || credits === undefined) return "Credits TBD";
    return `${credits.toLocaleString()} credits / mo`;
};

const FieldGrid = ({ data, title }: { data: GenericRecord | undefined; title: string }) => {
    const entries = Object.entries(data || {});
    return (
        <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
            <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">{title}</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-slate-600 dark:text-slate-300">
                {entries.length === 0 && <div className="text-slate-500">No data.</div>}
                {entries.map(([key, value]) => (
                    <div key={key} className="flex items-start justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-2">
                        <span className="text-slate-500">{key}</span>
                        <span className="text-right break-all">{renderFieldValue(value)}</span>
                    </div>
                ))}
            </div>
        </section>
    );
};

type TableRow = GenericRecord & { id?: string | number };

const DataTable = ({
    title,
    rows,
    columns
}: {
    title: string;
    rows: TableRow[];
    columns: { key: string; label: string; render?: (value: unknown, row: TableRow) => string }[];
}) => (
    <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
            <h4 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">{title}</h4>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{rows.length} total</span>
        </div>
        <div className="overflow-x-auto">
            <table className="w-full text-xs text-slate-600 dark:text-slate-300">
                <thead>
                    <tr className="text-slate-500 uppercase tracking-widest text-[10px]">
                        {columns.map((col) => (
                            <th key={col.key} className="text-left py-2 border-b border-slate-200 dark:border-slate-800">{col.label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan={columns.length} className="py-4 text-slate-500">No records.</td>
                        </tr>
                    )}
                    {rows.map((row, index) => {
                        const rowKey = typeof row.id === "string" || typeof row.id === "number" ? row.id : index;
                        return (
                            <tr key={rowKey} className="border-b border-slate-200 dark:border-slate-800">
                                {columns.map((col) => (
                                    <td key={col.key} className="py-2 pr-4">
                                        {col.render ? col.render(row[col.key], row) : renderFieldValue(row[col.key])}
                                    </td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    </section>
);

export default function UserDetailPage() {
    const { id } = useParams();
    const [user, setUser] = useState<UserDetail | null>(null);
    const [activity, setActivity] = useState<ActivityItem[]>([]);
    const [sessions, setSessions] = useState<GenericRecord[]>([]);
    const [payments, setPayments] = useState<GenericRecord[]>([]);
    const [questionHistory, setQuestionHistory] = useState<GenericRecord[]>([]);
    const [fullData, setFullData] = useState<FullUserData | null>(null);
    const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
    const [activeTab, setActiveTab] = useState("Profile Detail");
    const [loading, setLoading] = useState(true);
    const [noteContent, setNoteContent] = useState("");
    const [isSavingNote, setIsSavingNote] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isSavingProfile, setIsSavingProfile] = useState(false);
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    const getAuthHeaders = useCallback((includeJson = false) => {
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        if (includeJson) {
            (headers as Record<string, string>)["Content-Type"] = "application/json";
        }
        return headers;
    }, []);

    // Form states for updates
    const [newQuotaQuestions, setNewQuotaQuestions] = useState(0);
    const [newQuotaScans, setNewQuotaScans] = useState(0);
    const [newTier, setNewTier] = useState("");
    const [availablePlans, setAvailablePlans] = useState<{ id: number; name: string; slug: string }[]>([]);
    const [editFullName, setEditFullName] = useState("");
    const [editEmail, setEditEmail] = useState("");
    const [editAcademicLevel, setEditAcademicLevel] = useState("");
    const [editTimezone, setEditTimezone] = useState("");
    const [editProfileCountry, setEditProfileCountry] = useState("");
    const [editProfileProvince, setEditProfileProvince] = useState("");
    const [editGradeLevel, setEditGradeLevel] = useState("");
    const [editSchoolId, setEditSchoolId] = useState("");

    const fetchPlans = useCallback(async (signal?: AbortSignal) => {
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/plans`, { headers: getAuthHeaders(), signal });
            if (res.ok) {
                const data = await res.json();
                setAvailablePlans(data);
            }
        } catch (error) {
            if ((error as Error).name === "AbortError") return;
            console.error("Failed to fetch plans:", error);
        }
    }, [baseUrl, getAuthHeaders]);

    const fetchUserDetail = useCallback(async (signal?: AbortSignal) => {
        if (!id) return;
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}`, { headers: getAuthHeaders(), signal });
            if (res.ok) {
                const data = await res.json();
                setUser(data);
                setNewQuotaQuestions(data.quota_questions_total);
                setNewQuotaScans(data.quota_scans_total);
                setNewTier(data.subscription_tier);
                setEditFullName(data.full_name || "");
                setEditEmail(data.email || "");
                setEditAcademicLevel(data.academic_level || "");
            } else {
                throw new Error("Failed to load user profile.");
            }
        } catch (error) {
            if ((error as Error).name === "AbortError") {
                return;
            }
            console.error("Failed to fetch user detail:", error);
            setErrorMessage("Unable to load user profile. Please refresh.");
        } finally {
            setLoading(false);
        }
    }, [id, baseUrl, getAuthHeaders]);

    const fetchActivity = useCallback(async (signal?: AbortSignal) => {
        if (!id) return;
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/activity`, { headers: getAuthHeaders(), signal });
            if (res.ok) {
                const data = await res.json();
                setActivity(data);
            }
        } catch (error) {
            if ((error as Error).name === "AbortError") {
                return;
            }
            console.error("Failed to fetch activity:", error);
            setErrorMessage("Unable to load activity logs.");
        }
    }, [id, baseUrl, getAuthHeaders]);

    const fetchQuestionHistory = useCallback(async (signal?: AbortSignal) => {
        if (!id) return;
        try {
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/question-history`, { headers: getAuthHeaders(), signal });
            if (res.ok) {
                const data = await res.json();
                setQuestionHistory(Array.isArray(data) ? data : []);
                return;
            }
            if (res.status === 404) {
                setQuestionHistory([]);
                return;
            }
            const detail = await res.text();
            throw new Error(detail || `Question history failed: ${res.status}`);
        } catch (error) {
            if ((error as Error).name === "AbortError") {
                return;
            }
            console.error("Failed to fetch question history:", error);
            setErrorMessage("Unable to load question history.");
        }
    }, [id, baseUrl, getAuthHeaders]);

    const fetchFullUserData = useCallback(async (signal?: AbortSignal) => {
        if (!id) return;
        try {
            const headers = getAuthHeaders();
            const baseUrls = [baseUrl, "http://localhost:8000", "http://127.0.0.1:8000"];
            let lastError: string | null = null;
            for (const candidateBase of baseUrls) {
                try {
                    const res = await fetch(`${candidateBase}/api/v1/admin/users/${id}/full`, { headers, signal });
                    if (!res.ok) {
                        const detail = await res.text();
                        lastError = detail || res.statusText;
                        continue;
                    }
                    const data = await res.json();
                    setFullData(data);
                    setSessions(Array.isArray(data.sessions) ? data.sessions : []);
                    setPayments(Array.isArray(data.payments) ? data.payments : []);
                    setEditTimezone(data.user?.timezone || "");
                    setEditProfileCountry(data.user?.profile_country || "");
                    setEditProfileProvince(data.user?.profile_province_state || "");
                    setEditGradeLevel(data.user?.grade_level || "");
                    setEditSchoolId(data.user?.school_id ? String(data.user.school_id) : "");
                    if (!selectedSessionId && Array.isArray(data.sessions) && data.sessions.length > 0) {
                        setSelectedSessionId(data.sessions[0].id);
                    }
                    return;
                } catch (err) {
                    if ((err as Error).name === "AbortError") {
                        return;
                    }
                    lastError = (err as Error).message;
                }
            }
            throw new Error(lastError || "Failed to load full user data.");
        } catch (error) {
            if ((error as Error).name === "AbortError") {
                return;
            }
            console.error("Failed to fetch full user data:", error);
            setErrorMessage(`Unable to load full user data: ${(error as Error).message}`);
        }
    }, [id, baseUrl, getAuthHeaders, selectedSessionId]);

    useEffect(() => {
        if (!id) return;
        const controller = new AbortController();
        fetchUserDetail(controller.signal);
        fetchActivity(controller.signal);
        fetchFullUserData(controller.signal);
        fetchQuestionHistory(controller.signal);
        fetchPlans(controller.signal);
        return () => controller.abort();
    }, [id, fetchUserDetail, fetchActivity, fetchFullUserData, fetchQuestionHistory, fetchPlans]);

    const handleQuickAction = async (action: string) => {
        try {
            let res;
            setErrorMessage(null);
            if (action === "reset") res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/reset-password`, { method: "POST", headers: getAuthHeaders() });
            if (action === "resend") res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/resend-email`, { method: "POST", headers: getAuthHeaders() });
            if (action === "ban") res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/ban`, { method: "PATCH", headers: getAuthHeaders(true), body: JSON.stringify({ banned: user?.subscription_status !== "expired" }) });
            if (action === "delete") {
                if (!confirm("Are you sure?")) return;
                res = await fetch(`${baseUrl}/api/v1/admin/users/${id}`, { method: "DELETE", headers: getAuthHeaders() });
                if (res.ok) window.location.href = "/admin/users";
                return;
            }
            if (res?.ok) {
                alert(`${action} successful!`);
                fetchUserDetail();
            } else if (res) {
                throw new Error("Action failed.");
            }
        } catch (error) {
            console.error("Action failed:", error);
            setErrorMessage("Unable to complete admin action.");
        }
    };

    const handleAddNote = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!noteContent.trim()) return;

        setIsSavingNote(true);
        try {
            const adminName = localStorage.getItem("user_name") || "Admin";
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}/notes`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    admin_name: adminName,
                    content: noteContent
                })
            });
            if (res.ok) {
                setNoteContent("");
                fetchUserDetail();
            } else {
                throw new Error("Failed to add note.");
            }
        } catch (error) {
            console.error("Failed to add note:", error);
            setErrorMessage("Unable to add support note.");
        } finally {
            setIsSavingNote(false);
        }
    };

    const handleUpdateUser = async () => {
        try {
            setErrorMessage(null);
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}`, {
                method: "PATCH",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    quota_questions_total: newQuotaQuestions,
                    quota_scans_total: newQuotaScans,
                    subscription_tier: newTier
                })
            });
            if (res.ok) {
                alert("User updated successfully!");
                fetchUserDetail();
            } else {
                throw new Error("Update failed.");
            }
        } catch (error) {
            console.error("Failed to update user:", error);
            setErrorMessage("Unable to update user settings.");
        }
    };

    const handleProfileUpdate = async () => {
        try {
            setIsSavingProfile(true);
            setErrorMessage(null);
            const trimmedSchoolId = editSchoolId.trim();
            const parsedSchoolId = trimmedSchoolId === "" ? null : parseInt(trimmedSchoolId, 10);
            const payload = {
                full_name: editFullName,
                email: editEmail,
                academic_level: editAcademicLevel || null,
                timezone: editTimezone || null,
                profile_country: editProfileCountry || null,
                profile_province_state: editProfileProvince || null,
                grade_level: editGradeLevel || null,
                school_id: Number.isNaN(parsedSchoolId) ? null : parsedSchoolId
            };
            const res = await fetch(`${baseUrl}/api/v1/admin/users/${id}`, {
                method: "PATCH",
                headers: getAuthHeaders(true),
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                alert("Profile updated successfully!");
                fetchUserDetail();
                fetchFullUserData();
            } else {
                const detail = await res.text();
                throw new Error(detail || "Update failed.");
            }
        } catch (error) {
            console.error("Failed to update profile:", error);
            setErrorMessage("Unable to update profile details.");
        } finally {
            setIsSavingProfile(false);
        }
    };

    if (loading) return (
        <div className="flex-1 flex items-center justify-center bg-slate-50 dark:bg-[#0F172A]">
            <div className="flex flex-col items-center gap-4">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-admin-primary"></div>
                <p className="text-slate-400 font-medium">Loading secure student profiles...</p>
            </div>
        </div>
    );

    if (!user) return <div className="p-8 text-slate-900 dark:text-white">User not found</div>;

    const questionUsagePct = user.quota_questions_total > 0
        ? Math.min((user.questions_used / user.quota_questions_total) * 100, 100)
        : 0;
    const scanUsagePct = user.quota_scans_total > 0
        ? Math.min((user.scans_used / user.quota_scans_total) * 100, 100)
        : 0;
    const isVerified = Boolean(fullData?.user?.is_verified);
    const securityLabel = isVerified ? "Account Verified" : "Verification Pending";
    const securitySubLabel = isVerified ? "Identity Confirmed" : "Needs Review";

    return (
        <div className="flex h-screen bg-slate-50 dark:bg-[#0F172A] overflow-hidden">
            {/* Main Content Area */}
            <div className="flex-1 flex flex-col overflow-y-auto w-full">
                <header className="sticky top-0 z-10 bg-white/80 dark:bg-slate-50 dark:bg-[#0F172A]/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 p-8 flex flex-col gap-6">
                    {errorMessage && (
                        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs font-bold uppercase tracking-widest text-rose-300">
                            {errorMessage}
                        </div>
                    )}
                    <div className="flex justify-between items-start">
                        <div className="flex items-center gap-6">
                            <div className="relative group">
                                <div className="size-20 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl font-bold text-admin-primary border border-slate-700 shadow-xl overflow-hidden">
                                    {user.avatar_url ? (
                                        <Image
                                            src={user.avatar_url}
                                            alt={`${user.full_name} avatar`}
                                            width={80}
                                            height={80}
                                            className="w-full h-full object-cover"
                                            unoptimized
                                        />
                                    ) : (
                                        <span>{user.full_name[0]}</span>
                                    )}
                                </div>
                                <div className="absolute -bottom-1 -right-1 size-5 bg-emerald-500 rounded-full border-4 border-[#0F172A]"></div>
                            </div>
                            <div className="flex flex-col gap-1">
                                <div className="flex items-center gap-3">
                                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{user.full_name}</h1>
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
                            <button className="flex items-center gap-2 px-5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-900 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white text-sm font-bold rounded-xl transition-all border border-slate-200 dark:border-slate-700">
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
                        {["Profile Detail", "Session Logs", "Billing & Plan", "Security & Privacy", "Full Data"].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`pb-4 text-sm font-bold tracking-tight transition-all relative ${activeTab === tab ? "text-slate-900 dark:text-white" : "text-slate-500 hover:text-slate-300"
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
                        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col gap-4">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-admin-primary/10 text-admin-primary rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Usage</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Questions</span>
                            </div>
                            <div className="flex items-end justify-between">
                                <h3 className="text-4xl font-black text-slate-900 dark:text-white">{user.questions_used}</h3>
                                <p className="text-slate-400 text-sm font-bold mb-1">/ {user.quota_questions_total} total</p>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div className="h-full bg-admin-primary shadow-[0_0_8px_rgba(59,130,246,0.5)] transition-all duration-1000" style={{ width: `${questionUsagePct}%` }}></div>
                            </div>
                        </div>
                        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col gap-4">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-purple-500/10 text-purple-500 rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Vision</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">OCR Scans</span>
                            </div>
                            <div className="flex items-end justify-between">
                                <h3 className="text-4xl font-black text-slate-900 dark:text-white">{user.scans_used}</h3>
                                <p className="text-slate-400 text-sm font-bold mb-1">/ {user.quota_scans_total} total</p>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div className="h-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)] transition-all duration-1000" style={{ width: `${scanUsagePct}%` }}></div>
                            </div>
                        </div>
                        <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 p-6 rounded-2xl shadow-xl flex flex-col justify-between">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg font-bold text-xs uppercase tracking-widest leading-none">Security</div>
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className={`material-symbols-outlined text-3xl ${isVerified ? "text-emerald-500" : "text-amber-400"}`}>verified_user</span>
                                <div className="flex flex-col">
                                    <p className="text-slate-900 dark:text-white font-bold text-sm">{securityLabel}</p>
                                    <p className="text-slate-500 text-[10px] uppercase font-bold tracking-widest">{securitySubLabel}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {activeTab === "Profile Detail" && (
                        <>
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-2xl">
                                <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                                    <div>
                                        <h4 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">User Profile</h4>
                                        <p className="text-xs text-slate-500">Edit core identity, school, and location data.</p>
                                    </div>
                                    <button
                                        onClick={handleProfileUpdate}
                                        disabled={isSavingProfile}
                                        className="px-4 py-2 text-xs font-bold rounded-lg bg-admin-primary text-white hover:bg-admin-primary/90 disabled:opacity-60 disabled:cursor-not-allowed transition"
                                    >
                                        {isSavingProfile ? "Saving..." : "Save Profile"}
                                    </button>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Full Name</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editFullName}
                                            onChange={(e) => setEditFullName(e.target.value)}
                                            placeholder="Student Name"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Email</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            type="email"
                                            value={editEmail}
                                            onChange={(e) => setEditEmail(e.target.value)}
                                            placeholder="student@email.com"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Academic Level</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editAcademicLevel}
                                            onChange={(e) => setEditAcademicLevel(e.target.value)}
                                            placeholder="High School - Year 11"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Timezone</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editTimezone}
                                            onChange={(e) => setEditTimezone(e.target.value)}
                                            placeholder="UTC"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Profile Country</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editProfileCountry}
                                            onChange={(e) => setEditProfileCountry(e.target.value)}
                                            placeholder="USA or Canada"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Province / State</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editProfileProvince}
                                            onChange={(e) => setEditProfileProvince(e.target.value)}
                                            placeholder="CA-ON or USA-CA"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">Grade Level</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editGradeLevel}
                                            onChange={(e) => setEditGradeLevel(e.target.value)}
                                            placeholder="11"
                                        />
                                    </div>
                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-semibold text-slate-500">School ID</label>
                                        <input
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                            value={editSchoolId}
                                            onChange={(e) => setEditSchoolId(e.target.value)}
                                            placeholder="Numeric School ID"
                                        />
                                    </div>
                                </div>
                            </section>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                <section className="p-8 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl">
                                    <h4 className="text-lg font-bold text-slate-900 dark:text-white mb-6 tracking-tight">Account Management</h4>
                                    <div className="space-y-6">
                                        <div className="space-y-3">
                                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Quota Adjustment</p>
                                            <div className="flex items-center gap-4">
                                                <div className="flex-1 space-y-2">
                                                    <label className="text-xs text-slate-400 font-medium">Monthly Questions</label>
                                                    <input
                                                        className="w-full bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                                        type="number"
                                                        value={newQuotaQuestions}
                                                        onChange={(e) => setNewQuotaQuestions(parseInt(e.target.value))}
                                                    />
                                                </div>
                                                <div className="flex-1 space-y-2">
                                                    <label className="text-xs text-slate-400 font-medium">OCR Scan Limit</label>
                                                    <input
                                                        className="w-full bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
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
                                                className="w-full bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-white focus:ring-admin-primary"
                                                value={newTier}
                                                onChange={(e) => setNewTier(e.target.value)}
                                            >
                                                {availablePlans.map(plan => (
                                                    <option key={plan.id} value={plan.slug}>
                                                        {plan.name} ({plan.slug})
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                        <button
                                            onClick={handleUpdateUser}
                                            className="w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-900 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white text-sm font-bold rounded-xl transition-all border border-slate-200 dark:border-slate-700 mt-4"
                                        >
                                            Apply Changes & Notify User
                                        </button>
                                    </div>
                                </section>

                                <section className="p-8 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl flex flex-col justify-between">
                                    <div className="space-y-6">
                                        <h4 className="text-lg font-bold text-slate-900 dark:text-white mb-6 tracking-tight tracking-tight">Quick Actions</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <button onClick={() => handleQuickAction("reset")} className="flex items-center justify-center gap-2 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-900 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-700 transition-all">
                                                <span className="material-symbols-outlined text-base">lock_reset</span>
                                                Password Reset
                                            </button>
                                            <button onClick={() => handleQuickAction("resend")} className="flex items-center justify-center gap-2 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-900 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-700 transition-all">
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

                            {/* Activity Section */}
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                                <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                                        <span className="material-symbols-outlined text-slate-400">history</span>
                                        Recent Activity
                                    </h4>
                                    <button className="text-[11px] font-bold text-admin-primary uppercase tracking-widest hover:text-blue-400 transition-colors">See Performance Logs</button>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead>
                                            <tr className="border-b border-slate-200 dark:border-slate-800">
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
                                                        <button className="text-[10px] font-bold text-slate-500 hover:text-slate-900 dark:text-white uppercase tracking-widest transition-colors">View Details</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>

                            <DataTable
                                title="Question History (Prompt + Response)"
                                rows={questionHistory}
                                columns={[
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) },
                                    { key: "session_title", label: "Session" },
                                    { key: "prompt", label: "Prompt", render: (value) => renderShortText(value) },
                                    { key: "response", label: "Response", render: (value) => renderShortText(value, 320) },
                                    { key: "tokens_in", label: "In" },
                                    { key: "tokens_out", label: "Out" },
                                    { key: "tokens_total", label: "Total" },
                                    { key: "cost_usd", label: "Cost" },
                                    { key: "model", label: "Model" },
                                    { key: "status", label: "Status" }
                                ]}
                            />

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                <FieldGrid data={fullData?.user} title="User Fields" />
                                <FieldGrid data={fullData?.subscription} title="Subscription Fields" />
                                <FieldGrid data={fullData?.plan} title="Plan Fields" />
                                <FieldGrid data={fullData?.quota_overrides?.[0]} title="Quota Override (Latest)" />
                            </div>

                            <DataTable
                                title="Usage Logs"
                                rows={fullData?.usage_logs || []}
                                columns={[
                                    { key: "timestamp", label: "Timestamp", render: (value) => formatDateTime(value) },
                                    { key: "action_type", label: "Action" },
                                    { key: "tokens_used", label: "Tokens" }
                                ]}
                            />

                            <DataTable
                                title="Usage Ledger"
                                rows={fullData?.usage_ledger || []}
                                columns={[
                                    { key: "created_at", label: "Timestamp", render: (value) => formatDateTime(value) },
                                    { key: "transaction_type", label: "Type" },
                                    { key: "amount", label: "Amount" },
                                    { key: "balance_after", label: "Balance" },
                                    { key: "reference_id", label: "Reference" }
                                ]}
                            />
                            <DataTable
                                title="Request Events"
                                rows={fullData?.request_events || []}
                                columns={[
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) },
                                    { key: "request_id", label: "Request ID" },
                                    { key: "learning_mode", label: "Goal" },
                                    { key: "mode", label: "Style" },
                                    { key: "model", label: "Model" },
                                    { key: "tokens_in", label: "In" },
                                    { key: "tokens_out", label: "Out" },
                                    { key: "cost_usd", label: "Cost" },
                                    { key: "status", label: "Status" },
                                    { key: "error_type", label: "Error" }
                                ]}
                            />
                            <DataTable
                                title="Device Signup Logs"
                                rows={fullData?.device_signup_logs || []}
                                columns={[
                                    { key: "device_hash", label: "Device Hash" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) },
                                    { key: "user_id", label: "User ID" }
                                ]}
                            />

                            <DataTable
                                title="OCR Jobs"
                                rows={fullData?.ocr_jobs || []}
                                columns={[
                                    { key: "id", label: "Job ID" },
                                    { key: "status", label: "Status" },
                                    { key: "requested_engine", label: "Engine" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Voice Jobs"
                                rows={fullData?.voice_jobs || []}
                                columns={[
                                    { key: "id", label: "Job ID" },
                                    { key: "status", label: "Status" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Saved Solutions"
                                rows={fullData?.saved_solutions || []}
                                columns={[
                                    { key: "solution_id", label: "Solution ID" },
                                    { key: "saved_at", label: "Saved At", render: (value) => formatDateTime(value) },
                                    { key: "notes", label: "Notes" }
                                ]}
                            />

                            <DataTable
                                title="Uploads"
                                rows={fullData?.uploads || []}
                                columns={[
                                    { key: "id", label: "Upload ID" },
                                    { key: "storage_url", label: "Storage URL" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Crops"
                                rows={fullData?.crops || []}
                                columns={[
                                    { key: "id", label: "Crop ID" },
                                    { key: "upload_id", label: "Upload ID" },
                                    { key: "crop_image_hash", label: "Hash" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="OCR Artifacts"
                                rows={fullData?.ocr_artifacts || []}
                                columns={[
                                    { key: "id", label: "Artifact ID" },
                                    { key: "job_id", label: "Job ID" },
                                    { key: "engine_used", label: "Engine" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="OCR Questions"
                                rows={fullData?.ocr_questions || []}
                                columns={[
                                    { key: "id", label: "Question ID" },
                                    { key: "artifact_id", label: "Artifact ID" },
                                    { key: "prompt", label: "Prompt" }
                                ]}
                            />

                            <DataTable
                                title="OCR Choices"
                                rows={fullData?.ocr_choices || []}
                                columns={[
                                    { key: "id", label: "Choice ID" },
                                    { key: "question_id", label: "Question ID" },
                                    { key: "label", label: "Label" },
                                    { key: "text", label: "Text" }
                                ]}
                            />

                            <DataTable
                                title="OCR Figures"
                                rows={fullData?.ocr_figures || []}
                                columns={[
                                    { key: "id", label: "Figure ID" },
                                    { key: "artifact_id", label: "Artifact ID" },
                                    { key: "type", label: "Type" },
                                    { key: "description", label: "Description" }
                                ]}
                            />

                            <DataTable
                                title="OCR Confirmations"
                                rows={fullData?.ocr_confirmations || []}
                                columns={[
                                    { key: "id", label: "Confirmation ID" },
                                    { key: "artifact_id", label: "Artifact ID" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Voice Sessions"
                                rows={fullData?.voice_sessions || []}
                                columns={[
                                    { key: "id", label: "Session ID" },
                                    { key: "status", label: "Status" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Voice Audios"
                                rows={fullData?.voice_audios || []}
                                columns={[
                                    { key: "id", label: "Audio ID" },
                                    { key: "voice_session_id", label: "Session ID" },
                                    { key: "duration_ms", label: "Duration" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Voice Artifacts"
                                rows={fullData?.voice_artifacts || []}
                                columns={[
                                    { key: "id", label: "Artifact ID" },
                                    { key: "job_id", label: "Job ID" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Voice Confirmations"
                                rows={fullData?.voice_confirmations || []}
                                columns={[
                                    { key: "id", label: "Confirmation ID" },
                                    { key: "artifact_id", label: "Artifact ID" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                            <DataTable
                                title="Admin Notes"
                                rows={fullData?.admin_notes || []}
                                columns={[
                                    { key: "id", label: "Note ID" },
                                    { key: "admin_name", label: "Admin" },
                                    { key: "content", label: "Content" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />

                        </>
                    )}

                    {activeTab === "Session Logs" && (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <section className="lg:col-span-1 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                                <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">Sessions</h4>
                                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{sessions.length} total</span>
                                </div>
                                <div className="max-h-[520px] overflow-y-auto divide-y divide-slate-800">
                                    {sessions.map((sessionItem) => (
                                        <button
                                            key={sessionItem.id as number}
                                            onClick={() => setSelectedSessionId(sessionItem.id as number)}
                                            className={`w-full text-left px-5 py-4 hover:bg-slate-800/40 transition-colors ${selectedSessionId === sessionItem.id ? "bg-slate-800/40" : ""}`}
                                        >
                                            <div className="flex items-center justify-between gap-4">
                                                <div className="flex flex-col">
                                                    <span className="text-xs font-bold text-slate-900 dark:text-white">{(sessionItem.title as string) || "Untitled"}</span>
                                                    <span className="text-[10px] text-slate-500">{(sessionItem.subject as string) || "General"}</span>
                                                </div>
                                                <span className="text-[10px] text-slate-500">{sessionItem.created_at ? new Date(sessionItem.created_at as string).toLocaleDateString() : "n/a"}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </section>
                            <section className="lg:col-span-2 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
                                <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">Messages</h4>
                                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                                        {fullData?.messages?.length || 0} total
                                    </span>
                                </div>
                                <div className="max-h-[520px] overflow-y-auto divide-y divide-slate-800">
                                    {(fullData?.messages || [])
                                        .filter((message) => !selectedSessionId || message.session_id === selectedSessionId)
                                        .map((message) => (
                                            <div key={message.id as string} className="px-6 py-4">
                                                <div className="flex items-center justify-between">
                                                    <span className={`text-[10px] font-bold uppercase tracking-widest ${message.role === "assistant" ? "text-emerald-400" : "text-slate-400"}`}>
                                                        {message.role as string}
                                                    </span>
                                                    <span className="text-[10px] text-slate-500">
                                                        {message.created_at ? new Date(message.created_at as string).toLocaleString() : "n/a"}
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-300 mt-2 whitespace-pre-wrap break-words">
                                                    {message.content as string}
                                                </p>
                                            </div>
                                        ))}
                                    {selectedSessionId && (fullData?.messages || []).filter((m) => m.session_id === selectedSessionId).length === 0 && (
                                        <div className="p-6 text-xs text-slate-500">No messages for this session.</div>
                                    )}
                                </div>
                            </section>
                        </div>
                    )}

                    {activeTab === "Billing & Plan" && (
                        <div className="flex flex-col gap-6">
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-2xl">
                                <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                                    <div>
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-400 mb-1">Plan Summary</p>
                                        <h4 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                                            {formatPlanName(user.plan_name, user.plan_slug, user.subscription_tier)}
                                        </h4>
                                        <p className="text-xs uppercase tracking-[0.5em] text-slate-500">
                                            {user.plan_slug ? user.plan_slug.replace(/_/g, " ").toUpperCase() : user.subscription_tier.toUpperCase()}
                                        </p>
                                    </div>
                                    <div className="flex flex-col items-start md:items-end gap-2">
                                        <span className="text-[10px] uppercase tracking-[0.4em] text-slate-500">Status</span>
                                        <span className="px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border border-slate-200 dark:border-slate-700">
                                            {user.subscription_status.toUpperCase()}
                                        </span>
                                    </div>
                                </div>
                                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                    <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800">
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-400">Monthly Price</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white">{formatCurrencyFromCents(user.plan_price_monthly_cents)}</p>
                                    </div>
                                    <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800">
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-400">Credits / mo</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white">{formatCreditsLabel(user.plan_credits_per_month)}</p>
                                    </div>
                                    <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800">
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-400">Plan ID</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white">{user.plan_id ?? "n/a"}</p>
                                    </div>
                                    <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-2xl border border-slate-100 dark:border-slate-800">
                                        <p className="text-[10px] uppercase tracking-[0.4em] text-slate-400">Subscription ID</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white">{user.subscription_id ?? "n/a"}</p>
                                    </div>
                                </div>
                            </section>
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <FieldGrid title="Subscription Fields" data={fullData?.subscription} />
                                <FieldGrid title="Plan Fields" data={fullData?.plan} />
                                <DataTable
                                    title="Payments"
                                    rows={payments}
                                    columns={[
                                        { key: "created_at", label: "Date", render: (value) => formatDateTime(value) },
                                        { key: "amount", label: "Amount" },
                                        { key: "currency", label: "Currency" },
                                        { key: "status", label: "Status" },
                                        { key: "transaction_id", label: "Transaction" }
                                    ]}
                                />
                                <DataTable
                                    title="Ledger Entries"
                                    rows={fullData?.usage_ledger || []}
                                    columns={[
                                        { key: "created_at", label: "Date", render: (value) => formatDateTime(value) },
                                        { key: "transaction_type", label: "Type" },
                                        { key: "amount", label: "Amount" },
                                        { key: "balance_after", label: "Balance" },
                                        { key: "reference_id", label: "Reference" }
                                    ]}
                                />
                            </div>
                        </div>
                    )}

                    {activeTab === "Security & Privacy" && (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <FieldGrid
                                title="Security Fields"
                                data={{
                                    ip_address: fullData?.user?.ip_address,
                                    last_ip: fullData?.user?.last_ip,
                                    session_token: fullData?.user?.session_token,
                                    is_verified: fullData?.user?.is_verified,
                                    verification_token: fullData?.user?.verification_token,
                                    last_active_at: fullData?.user?.last_active_at,
                                    created_at: fullData?.user?.created_at,
                                    country: fullData?.user?.country,
                                    timezone: fullData?.user?.timezone
                                }}
                            />
                            <DataTable
                                title="Recent Sessions"
                                rows={(fullData?.sessions || []).slice(0, 20)}
                                columns={[
                                    { key: "id", label: "Session ID" },
                                    { key: "title", label: "Title" },
                                    { key: "subject", label: "Subject" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />
                            <DataTable
                                title="OCR Audit Events"
                                rows={(fullData?.ocr_audit_events || []).slice(0, 20)}
                                columns={[
                                    { key: "id", label: "Event ID" },
                                    { key: "routing_engine_chosen", label: "Engine" },
                                    { key: "provider_model", label: "Model" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />
                            <DataTable
                                title="Voice Sessions"
                                rows={(fullData?.voice_sessions || []).slice(0, 20)}
                                columns={[
                                    { key: "id", label: "Session ID" },
                                    { key: "status", label: "Status" },
                                    { key: "preferred_stt", label: "STT" },
                                    { key: "created_at", label: "Created", render: (value) => formatDateTime(value) }
                                ]}
                            />
                        </div>
                    )}

                    {activeTab === "Full Data" && (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
                                <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">User + Subscription</h4>
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">
                                    {JSON.stringify({ user: fullData?.user, subscription: fullData?.subscription, plan: fullData?.plan }, null, 2)}
                                </pre>
                            </section>
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
                                <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">Usage + Ledger</h4>
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">
                                    {JSON.stringify({ usage_logs: fullData?.usage_logs, usage_ledger: fullData?.usage_ledger }, null, 2)}
                                </pre>
                            </section>
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
                                <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">OCR Data</h4>
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">
                                    {JSON.stringify({
                                        uploads: fullData?.uploads,
                                        crops: fullData?.crops,
                                        jobs: fullData?.ocr_jobs,
                                        artifacts: fullData?.ocr_artifacts,
                                        questions: fullData?.ocr_questions,
                                        choices: fullData?.ocr_choices,
                                        figures: fullData?.ocr_figures,
                                        confirmations: fullData?.ocr_confirmations,
                                        audit_events: fullData?.ocr_audit_events
                                    }, null, 2)}
                                </pre>
                            </section>
                            <section className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
                                <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">Voice Data</h4>
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">
                                    {JSON.stringify({
                                        sessions: fullData?.voice_sessions,
                                        audios: fullData?.voice_audios,
                                        jobs: fullData?.voice_jobs,
                                        artifacts: fullData?.voice_artifacts,
                                        confirmations: fullData?.voice_confirmations
                                    }, null, 2)}
                                </pre>
                            </section>
                            <section className="lg:col-span-2 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl">
                                <h4 className="text-base font-bold text-slate-900 dark:text-white mb-4 tracking-tight">Raw JSON (All)</h4>
                                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words">
                                    {JSON.stringify(fullData, null, 2)}
                                </pre>
                            </section>
                        </div>
                    )}
                </div>
            </div>

            {/* Support Notes Sidebar */}
            <aside className="w-80 flex-shrink-0 bg-white dark:bg-[#0c1222] border-l border-slate-200 dark:border-slate-800 flex flex-col p-6 overflow-y-auto sticky top-0 h-screen shadow-2xl">
                <div className="flex items-center justify-between mb-8">
                    <h4 className="text-base font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                        <span className="material-symbols-outlined text-admin-primary">sticky_note_2</span>
                        Support Notes
                    </h4>
                    <span className="bg-slate-800 text-slate-400 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest">{user.notes.length} NOTES</span>
                </div>

                <div className="flex-1 flex flex-col gap-6">
                    {user.notes.map((note) => (
                        <div key={note.id} className="p-4 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-xl space-y-3 shadow-md relative group">
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
                            className="w-full bg-white dark:bg-[#0c1222] border-slate-200 dark:border-slate-800 rounded-xl p-4 text-xs text-slate-900 dark:text-white placeholder:text-slate-600 focus:ring-admin-primary h-24 resize-none transition-all focus:border-admin-primary"
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
