"use client";

import { useState, useEffect } from "react";
import StudentLayout from "@/components/layout/StudentLayout";
import { useToast } from "@/components/ui/ToastProvider";
import { parseApiError } from "@/lib/api";
import { fetchWalletPrograms, fetchWalletSummary, WalletProgramEnrollment, WalletSummary } from "@/lib/wallet";

type TabId = 'profile' | 'location' | 'preferences' | 'billing' | 'security';

interface ProfileData {
    id: number;
    full_name: string;
    email: string;
    academic_level: string;
    timezone: string;
    theme: string;
    preferred_language: string;
    solving_mode: string;
    subscription_tier?: string;
    subscription_status?: string;
    // Location profile
    profile_country?: string;
    profile_province_state?: string;
    grade_level?: string;
    school_id?: number;
    school_name?: string;
    usage: {
        questions_count: number;
        questions_total: number;
        scans_count: number;
        scans_total: number;
    };
}

interface SchoolSearchResult {
    id: number;
    school_name: string;
    city: string | null;
    district: string | null;
}

export default function ProfilePage() {
    const { pushToast } = useToast();
    const [activeTab, setActiveTab] = useState<TabId>('profile');
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);
    const [walletPrograms, setWalletPrograms] = useState<WalletProgramEnrollment[]>([]);
    const [walletLoading, setWalletLoading] = useState(true);
    const [walletError, setWalletError] = useState<string | null>(null);

    // Form states
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [academicLevel, setAcademicLevel] = useState("");
    const [timezone, setTimezone] = useState("");
    const [theme, setTheme] = useState("");
    const [language, setLanguage] = useState("");
    const [solvingMode, setSolvingMode] = useState("");

    // Location profile states
    const [profileCountry, setProfileCountry] = useState("");
    const [profileProvinceState, setProfileProvinceState] = useState("");
    const [gradeLevel, setGradeLevel] = useState("");
    const [schoolId, setSchoolId] = useState<number | null>(null);
    const [selectedSchoolName, setSelectedSchoolName] = useState("");

    // Dropdown options
    const [provinces, setProvinces] = useState<string[]>([]);
    const [provinceLabel, setProvinceLabel] = useState("Province/State");
    const [grades, setGrades] = useState<string[]>([]);

    // School search
    const [schoolQuery, setSchoolQuery] = useState("");
    const [schoolResults, setSchoolResults] = useState<SchoolSearchResult[]>([]);
    const [schoolSearching, setSchoolSearching] = useState(false);
    const [showSchoolDropdown, setShowSchoolDropdown] = useState(false);
    
    // WhatsApp integration
    const [whatsappSecret, setWhatsappSecret] = useState("");
    const [showWhatsappSecret, setShowWhatsappSecret] = useState(false);
    const [whatsappEnabled, setWhatsappEnabled] = useState(true);

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;

        fetch(`${apiBaseUrl}/api/v1/user/profile?user_id=${userId}`)
            .then(res => res.json())
            .then(data => {
                setProfile(data);
                setFullName(data.full_name);
                setEmail(data.email);
                setAcademicLevel(data.academic_level || "Undergraduate - Year 2");
                setTimezone(data.timezone || "GMT (UTC +0:00)");
                setTheme(data.theme || "light");
                setLanguage(data.preferred_language || "English (US)");
                setSolvingMode(data.solving_mode || "Full Solution");
                // Location profile
                setProfileCountry(data.profile_country || "");
                setProfileProvinceState(data.profile_province_state || "");
                setGradeLevel(data.grade_level || "");
                setSchoolId(data.school_id || null);
                setSelectedSchoolName(data.school_name || "");
                setSchoolQuery(data.school_name || "");
                // WhatsApp
                setWhatsappSecret(data.whatsapp_secret || "");
                setWhatsappEnabled(data.whatsapp_enabled !== false);
                setLoading(false);
            })
            .catch(err => {
                console.error("Error fetching profile:", err);
                setLoading(false);
            });

        // Fetch grade levels
        fetch(`${apiBaseUrl}/api/v1/locations/grades`)
            .then(res => res.json())
            .then(data => setGrades(data.grades || []))
            .catch(console.error);
    }, [apiBaseUrl]);

    useEffect(() => {
        let active = true;
        const loadWallet = async () => {
            try {
                const [summary, programs] = await Promise.all([
                    fetchWalletSummary(),
                    fetchWalletPrograms(25, 0),
                ]);
                if (!active) return;
                setWalletSummary(summary);
                setWalletPrograms(programs.items || []);
                setWalletError(null);
            } catch (err) {
                if (!active) return;
                const message = err instanceof Error ? err.message : "Unable to load wallet";
                const requestId = err && typeof err === "object" && "requestId" in err ? (err as { requestId?: string }).requestId : undefined;
                setWalletError(message);
                pushToast({
                    type: "error",
                    title: "Wallet unavailable",
                    message,
                    requestId,
                });
            } finally {
                if (active) setWalletLoading(false);
            }
        };
        void loadWallet();
        return () => {
            active = false;
        };
    }, [pushToast]);

    // Fetch provinces when country changes
    useEffect(() => {
        if (!profileCountry) {
            setProvinces([]);
            setProvinceLabel("Province/State");
            return;
        }

        fetch(`${apiBaseUrl}/api/v1/locations/provinces?country=${profileCountry}`)
            .then(res => res.json())
            .then(data => {
                setProvinces(data.provinces || []);
                setProvinceLabel(data.label || "Province/State");
                // Reset province selection if not in new list
                if (data.provinces && !data.provinces.includes(profileProvinceState)) {
                    setProfileProvinceState("");
                    setSchoolId(null);
                    setSelectedSchoolName("");
                }
            })
            .catch(console.error);
    }, [profileCountry, profileProvinceState, apiBaseUrl]);

    // School search with debounce
    useEffect(() => {
        if (!profileCountry || !profileProvinceState || schoolQuery.length < 2) {
            setSchoolResults([]);
            return;
        }

        const timer = setTimeout(() => {
            setSchoolSearching(true);
            fetch(`${apiBaseUrl}/api/v1/schools/search?country=${profileCountry}&province_state=${profileProvinceState}&q=${encodeURIComponent(schoolQuery)}&limit=10`)
                .then(res => res.json())
                .then(data => {
                    setSchoolResults(Array.isArray(data) ? data : []);
                    setSchoolSearching(false);
                })
                .catch(err => {
                    console.error(err);
                    setSchoolSearching(false);
                });
        }, 300); // 300ms debounce

        return () => clearTimeout(timer);
    }, [schoolQuery, profileCountry, profileProvinceState, apiBaseUrl]);

    const handleSaveProfile = async () => {
        const userId = localStorage.getItem("user_id");
        setSaving(true);
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
        try {
            const res = await fetch(`${apiBaseUrl}/api/v1/user/profile?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    full_name: fullName,
                    email: email,
                    academic_level: academicLevel,
                    timezone: timezone
                })
            });
            if (res.ok) {
                pushToast({
                    type: "success",
                    title: "Profile updated",
                    message: "Your profile details were saved.",
                });
                // Update local storage if needed
                localStorage.setItem("user_name", fullName);
            }
        } catch (err) {
            console.error(err);
            pushToast({
                type: "error",
                title: "Profile update failed",
                message: err instanceof Error ? err.message : "Unexpected error",
            });
        } finally {
            setSaving(false);
        }
    };

    const handleSavePreferences = async () => {
        const userId = localStorage.getItem("user_id");
        setSaving(true);
        try {
            const res = await fetch(`${apiBaseUrl}/api/v1/user/preferences?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    theme: theme,
                    preferred_language: language,
                    solving_mode: solvingMode
                })
            });
            if (res.ok) {
                pushToast({
                    type: "success",
                    title: "Preferences updated",
                    message: "Your preferences were saved.",
                });
                // Apply theme immediately
                if (theme === 'dark') {
                    document.documentElement.classList.add('dark');
                } else if (theme === 'light') {
                    document.documentElement.classList.remove('dark');
                }
            }
        } catch (err) {
            console.error(err);
            pushToast({
                type: "error",
                title: "Preferences update failed",
                message: err instanceof Error ? err.message : "Unexpected error",
            });
        } finally {
            setSaving(false);
        }
    };

    const handleSaveLocation = async () => {
        const userId = localStorage.getItem("user_id");

        // Validate required fields
        if (!profileCountry || !profileProvinceState || !gradeLevel) {
            pushToast({
                type: "error",
                title: "Missing location fields",
                message: "Please select your Country, Province/State, and Grade Level.",
            });
            return;
        }
        if (schoolQuery.trim().length > 0 && !schoolId) {
            pushToast({
                type: "error",
                title: "Select a school",
                message: "Please select a school from the dropdown list before saving.",
            });
            return;
        }

        setSaving(true);
        try {
            const res = await fetch(`${apiBaseUrl}/api/v1/user/profile-location?user_id=${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile_country: profileCountry,
                    profile_province_state: profileProvinceState,
                    grade_level: gradeLevel,
                    school_id: schoolId
                })
            });

            if (res.ok) {
                const data = await res.json();
                pushToast({
                    type: "success",
                    title: "Location profile saved",
                    message: "Your tutor will now adapt to your curriculum.",
                });
                // Update local profile
                if (profile) {
                    setProfile({
                        ...profile,
                        profile_country: data.profile_country,
                        profile_province_state: data.profile_province_state,
                        grade_level: data.grade_level,
                        school_id: data.school_id,
                        school_name: data.school_name || null
                    });
                }
                setSchoolId(data.school_id || null);
                setSelectedSchoolName(data.school_name || "");
                setSchoolQuery(data.school_name || "");
            } else {
                const err = await parseApiError(res);
                pushToast({
                    type: "error",
                    title: "Location update failed",
                    message: err.message,
                    requestId: err.requestId,
                });
            }
        } catch (err) {
            console.error(err);
            pushToast({
                type: "error",
                title: "Location update failed",
                message: err instanceof Error ? err.message : "Unexpected error",
            });
        } finally {
            setSaving(false);
        }
    };

    const handleSelectSchool = (school: SchoolSearchResult) => {
        setSchoolId(school.id);
        setSelectedSchoolName(school.school_name);
        setSchoolQuery(school.school_name);
        setShowSchoolDropdown(false);
    };

    const handleClearSchool = () => {
        setSchoolId(null);
        setSelectedSchoolName("");
        setSchoolQuery("");
    };

    // If profile has school_id but API payload misses school_name, resolve by ID.
    useEffect(() => {
        if (!schoolId || selectedSchoolName) return;
        fetch(`${apiBaseUrl}/api/v1/schools/${schoolId}`)
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data?.school_name) {
                    setSelectedSchoolName(data.school_name);
                    setSchoolQuery(data.school_name);
                }
            })
            .catch(() => { /* best-effort hydration */ });
    }, [schoolId, selectedSchoolName, apiBaseUrl]);

    if (loading) {
        return (
            <StudentLayout>
                <div className="p-8 flex items-center justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
            </StudentLayout>
        );
    }

    // Calculate profile completeness
    const calculateProfileCompleteness = () => {
        const fields = [
            { name: 'Full Name', filled: !!fullName },
            { name: 'Email', filled: !!email },
            { name: 'Country', filled: !!profileCountry },
            { name: 'Province/State', filled: !!profileProvinceState },
            { name: 'Grade Level', filled: !!gradeLevel },
            { name: 'Academic Level', filled: !!academicLevel },
            { name: 'Timezone', filled: !!timezone },
        ];

        const filledCount = fields.filter(f => f.filled).length;
        const percentage = Math.round((filledCount / fields.length) * 100);
        const missingFields = fields.filter(f => !f.filled).map(f => f.name);

        return { percentage, filledCount, total: fields.length, missingFields };
    };

    const profileCompleteness = calculateProfileCompleteness();
    const isLocationComplete = !!profileCountry && !!profileProvinceState && !!gradeLevel;

    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'profile', label: 'Profile', icon: 'person' },
        { id: 'location', label: 'Location & School', icon: 'school' },
        { id: 'preferences', label: 'Preferences', icon: 'settings' },
        { id: 'billing', label: 'Wallet & Programs', icon: 'credit_card' },
        { id: 'security', label: 'Security', icon: 'shield' },
    ];

    return (
        <StudentLayout>
            <div className="max-w-4xl mx-auto py-10 px-8">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-4xl font-black tracking-tight mb-2">Settings & Preferences</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-lg">Personalize your learning experience and manage account details.</p>
                </div>

                {/* Profile Completeness Indicator */}
                {profileCompleteness.percentage < 100 && (
                    <div className="mb-8 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl p-5 animate-in fade-in slide-in-from-top-4 duration-300">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="relative">
                                        <div className="size-12 rounded-full bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center">
                                            <span className="text-lg font-black text-amber-600 dark:text-amber-400">{profileCompleteness.percentage}%</span>
                                        </div>
                                        <svg className="absolute inset-0 -rotate-90" viewBox="0 0 48 48">
                                            <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" strokeWidth="4" className="text-amber-200 dark:text-amber-800" />
                                            <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" strokeWidth="4"
                                                strokeDasharray={`${profileCompleteness.percentage * 1.26} 126`}
                                                className="text-amber-500" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-amber-900 dark:text-amber-100">Complete Your Profile</h3>
                                        <p className="text-sm text-amber-700 dark:text-amber-300">
                                            {profileCompleteness.filledCount} of {profileCompleteness.total} fields complete
                                        </p>
                                    </div>
                                </div>

                                {profileCompleteness.missingFields.length > 0 && (
                                    <div className="text-sm text-amber-700 dark:text-amber-300">
                                        <span className="font-medium">Missing: </span>
                                        {profileCompleteness.missingFields.join(', ')}
                                    </div>
                                )}
                            </div>

                            {!isLocationComplete && (
                                <button
                                    onClick={() => setActiveTab('location')}
                                    className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-bold rounded-xl transition-all flex items-center gap-2 shrink-0"
                                >
                                    <span className="material-symbols-outlined text-sm">school</span>
                                    Set Location
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Success state when complete */}
                {profileCompleteness.percentage === 100 && (
                    <div className="mb-8 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-4 flex items-center gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
                        <div className="size-10 rounded-full bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                            <span className="material-symbols-outlined text-green-600">check_circle</span>
                        </div>
                        <div>
                            <h3 className="font-bold text-green-900 dark:text-green-100">Profile Complete!</h3>
                            <p className="text-sm text-green-700 dark:text-green-300">Your AI tutor is fully personalized to your curriculum.</p>
                        </div>
                    </div>
                )}

                {/* Tab Navigation (Custom implementation for settings) */}
                <div className="flex gap-4 mb-8">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === tab.id
                                ? "bg-primary text-white shadow-lg shadow-primary/20"
                                : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                                }`}
                        >
                            <span className="material-symbols-outlined text-sm">{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="space-y-10">
                    {activeTab === 'profile' && (
                        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-300">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800">
                                <h2 className="text-xl font-bold">Profile Information</h2>
                                <p className="text-slate-500 text-sm">Update your account details and academic level.</p>
                            </div>
                            <div className="p-6 space-y-6">
                                <div className="flex gap-6 items-center pb-4 border-b border-slate-100 dark:border-slate-800">
                                    <div className="relative">
                                        <div className="size-20 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-2xl overflow-hidden">
                                            {fullName.split(' ').map(n => n[0]).join('') || "JS"}
                                        </div>
                                        <button className="absolute bottom-0 right-0 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 size-7 rounded-full flex items-center justify-center hover:bg-slate-50 transition-colors">
                                            <span className="material-symbols-outlined text-sm">edit</span>
                                        </button>
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold">{fullName}</h3>
                                        <p className="text-sm text-slate-500">{email}</p>
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold">Full Name</label>
                                        <input
                                            value={fullName}
                                            onChange={(e) => setFullName(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none"
                                            type="text"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold">Email Address</label>
                                        <input
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none"
                                            type="email"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold">Academic Level</label>
                                        <select
                                            value={academicLevel}
                                            onChange={(e) => setAcademicLevel(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none"
                                        >
                                            <option>High School - Year 12</option>
                                            <option>Undergraduate - Year 1</option>
                                            <option>Undergraduate - Year 2</option>
                                            <option>Postgraduate</option>
                                        </select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold">Timezone</label>
                                        <select
                                            value={timezone}
                                            onChange={(e) => setTimezone(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none"
                                        >
                                            <option>GMT (UTC +0:00)</option>
                                            <option>EST (UTC -5:00)</option>
                                            <option>GST (UTC +4:00)</option>
                                        </select>
                                    </div>
                                </div>
                                <div className="flex justify-end pt-4">
                                    <button
                                        onClick={handleSaveProfile}
                                        disabled={saving}
                                        className="px-8 py-3 bg-primary text-white text-sm font-bold rounded-xl hover:shadow-lg hover:bg-blue-700 transition-all disabled:opacity-50"
                                    >
                                        {saving ? "Saving..." : "Save Profile"}
                                    </button>
                                </div>
                            </div>
                        </section>
                    )}

                    {activeTab === 'location' && (
                        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-300">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800">
                                <div className="flex items-center gap-3 mb-2">
                                    <span className="material-symbols-outlined text-primary text-2xl">school</span>
                                    <h2 className="text-xl font-bold">Location & School</h2>
                                </div>
                                <p className="text-slate-500 text-sm">
                                    Tell us where you study so your AI tutor can adapt to your local curriculum,
                                    use familiar units (metric/imperial), and match your grade level.
                                </p>
                            </div>

                            <div className="p-6 space-y-6">
                                {/* Info Banner */}
                                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded-xl p-4 flex gap-3">
                                    <span className="material-symbols-outlined text-blue-600 dark:text-blue-400">info</span>
                                    <div>
                                        <p className="text-sm text-blue-700 dark:text-blue-300 font-medium">
                                            Why does this matter?
                                        </p>
                                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                                            Different regions teach math differently. A Grade 10 student in Ontario learns different topics
                                            than one in California. Your tutor will use terminology and methods appropriate for your curriculum.
                                        </p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Country */}
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold flex items-center gap-1">
                                            Country
                                            <span className="text-red-500">*</span>
                                        </label>
                                        <select
                                            value={profileCountry}
                                            onChange={(e) => {
                                                setProfileCountry(e.target.value);
                                                setProfileProvinceState("");
                                                setSchoolId(null);
                                                setSelectedSchoolName("");
                                                setSchoolQuery("");
                                            }}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none cursor-pointer"
                                        >
                                            <option value="">Select your country...</option>
                                            <option value="USA">United States</option>
                                            <option value="Canada">Canada</option>
                                        </select>
                                    </div>

                                    {/* Province/State */}
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold flex items-center gap-1">
                                            {provinceLabel}
                                            <span className="text-red-500">*</span>
                                        </label>
                                        <select
                                            value={profileProvinceState}
                                            onChange={(e) => {
                                                setProfileProvinceState(e.target.value);
                                                setSchoolId(null);
                                                setSelectedSchoolName("");
                                                setSchoolQuery("");
                                            }}
                                            disabled={!profileCountry || provinces.length === 0}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            <option value="">Select {provinceLabel.toLowerCase()}...</option>
                                            {provinces.map(p => (
                                                <option key={p} value={p}>{p}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Grade Level */}
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold flex items-center gap-1">
                                            Grade Level
                                            <span className="text-red-500">*</span>
                                        </label>
                                        <select
                                            value={gradeLevel}
                                            onChange={(e) => setGradeLevel(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none cursor-pointer"
                                        >
                                            <option value="">Select your grade...</option>
                                            {grades.map(g => (
                                                <option key={g} value={g}>{g}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* School Search (Optional) */}
                                    <div className="space-y-2 relative">
                                        <label className="text-sm font-bold flex items-center gap-1">
                                            School
                                            <span className="text-slate-400 text-xs font-normal">(optional)</span>
                                        </label>
                                        <div className="relative">
                                            <input
                                                value={schoolQuery}
                                                onChange={(e) => {
                                                    setSchoolQuery(e.target.value);
                                                    setShowSchoolDropdown(true);
                                                    if (schoolId && e.target.value !== selectedSchoolName) {
                                                        setSchoolId(null);
                                                        setSelectedSchoolName("");
                                                    }
                                                }}
                                                onFocus={() => setShowSchoolDropdown(true)}
                                                placeholder={profileCountry && profileProvinceState ? "Type to search schools..." : "Select country and province first"}
                                                disabled={!profileCountry || !profileProvinceState}
                                                className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 pr-10 text-sm focus:ring-2 focus:ring-primary outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                                            />
                                            {schoolId ? (
                                                <button
                                                    onClick={handleClearSchool}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                                >
                                                    <span className="material-symbols-outlined text-sm">close</span>
                                                </button>
                                            ) : schoolSearching ? (
                                                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                                                </div>
                                            ) : (
                                                <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">search</span>
                                            )}
                                        </div>

                                        {/* School Dropdown */}
                                        {showSchoolDropdown && schoolResults.length > 0 && (
                                            <div className="absolute z-50 w-full mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg max-h-60 overflow-y-auto">
                                                {schoolResults.map(school => (
                                                    <button
                                                        key={school.id}
                                                        onClick={() => handleSelectSchool(school)}
                                                        className="w-full text-left px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700 border-b border-slate-100 dark:border-slate-700 last:border-0 transition-colors"
                                                    >
                                                        <p className="text-sm font-medium truncate">{school.school_name}</p>
                                                        {school.city && (
                                                            <p className="text-xs text-slate-500">{school.city}{school.district ? `, ${school.district}` : ''}</p>
                                                        )}
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Selected School Badge */}
                                {schoolId && selectedSchoolName && (
                                    <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                                        <span className="material-symbols-outlined text-green-600">check_circle</span>
                                        <span className="text-sm text-green-700 dark:text-green-300">
                                            Selected: <strong>{selectedSchoolName}</strong>
                                        </span>
                                    </div>
                                )}

                                {/* Save Button */}
                                <div className="flex justify-end pt-4">
                                    <button
                                        onClick={handleSaveLocation}
                                        disabled={saving || !profileCountry || !profileProvinceState || !gradeLevel}
                                        className="px-8 py-3 bg-primary text-white text-sm font-bold rounded-xl hover:shadow-lg hover:bg-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                    >
                                        {saving ? (
                                            <>
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <span className="material-symbols-outlined text-sm">save</span>
                                                Save Location
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </section>
                    )}

                    {activeTab === 'preferences' && (
                        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-300">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800">
                                <h2 className="text-xl font-bold">Learning Preferences</h2>
                                <p className="text-slate-500 text-sm">Configure how uask.ai assists you with your problems.</p>
                            </div>
                            <div className="p-6 space-y-8">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <div className="space-y-3">
                                        <label className="text-sm font-bold">System Theme</label>
                                        <div className="flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl">
                                            {['light', 'dark', 'auto'].map((t) => (
                                                <button
                                                    key={t}
                                                    onClick={() => setTheme(t)}
                                                    className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-bold rounded-lg transition-all ${theme === t
                                                        ? "bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600"
                                                        : "text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800"
                                                        }`}
                                                >
                                                    <span className="material-symbols-outlined text-sm">
                                                        {t === 'light' ? 'light_mode' : t === 'dark' ? 'dark_mode' : 'desktop_windows'}
                                                    </span>
                                                    {t.charAt(0).toUpperCase() + t.slice(1)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="space-y-3">
                                        <label className="text-sm font-bold">Preferred Language</label>
                                        <select
                                            value={language}
                                            onChange={(e) => setLanguage(e.target.value)}
                                            className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-xl h-12 px-4 text-sm font-medium focus:ring-2 focus:ring-primary outline-none"
                                        >
                                            <option>English (US)</option>
                                            <option>Arabic</option>
                                            <option>French</option>
                                        </select>
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    <label className="text-sm font-bold flex items-center gap-2">
                                        Default Solving Mode
                                        <span className="material-symbols-outlined text-xs text-slate-400 cursor-help">help</span>
                                    </label>
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        {[
                                            { id: 'Full Solution', label: 'Full Solution', icon: 'auto_awesome', desc: 'Complete breakdown immediately.' },
                                            { id: 'Hint Ladder', label: 'Hint Ladder', icon: 'format_list_numbered', desc: 'Reveal hints one at a time.' },
                                            { id: 'Socratic', label: 'Socratic', icon: 'psychology', desc: 'AI asks guiding questions.' },
                                        ].map((mode) => (
                                            <div
                                                key={mode.id}
                                                onClick={() => setSolvingMode(mode.id)}
                                                className={`relative flex flex-col p-4 border-2 rounded-2xl cursor-pointer transition-all ${solvingMode === mode.id
                                                    ? "border-primary bg-primary/5 ring-4 ring-primary/5"
                                                    : "border-slate-100 dark:border-slate-800 hover:border-primary/50"
                                                    }`}
                                            >
                                                <div className="flex justify-between items-start mb-2">
                                                    <span className={`material-symbols-outlined ${solvingMode === mode.id ? "text-primary" : "text-slate-400"}`}>{mode.icon}</span>
                                                    {solvingMode === mode.id && (
                                                        <div className="bg-primary size-4 rounded-full flex items-center justify-center">
                                                            <span className="material-symbols-outlined text-[10px] text-white font-bold">check</span>
                                                        </div>
                                                    )}
                                                </div>
                                                <p className="text-sm font-bold">{mode.label}</p>
                                                <p className="text-[11px] text-slate-500 mt-1">{mode.desc}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* WhatsApp Integration Section */}
                                <div className="space-y-3 pt-6 border-t border-slate-200 dark:border-slate-800">
                                    <div className="flex items-center gap-3 mb-4">
                                        <span className="material-symbols-outlined text-green-500 text-2xl">whatsapp</span>
                                        <div>
                                            <label className="text-sm font-bold">WhatsApp Integration</label>
                                            <p className="text-xs text-slate-500">Get math help via WhatsApp on your phone</p>
                                        </div>
                                    </div>
                                    
                                    <div className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border border-green-200 dark:border-green-800 rounded-xl p-5 space-y-4">
                                        <div className="flex items-start gap-3">
                                            <span className="material-symbols-outlined text-green-600 dark:text-green-400 text-xl">info</span>
                                            <div className="flex-1">
                                                <p className="text-sm text-green-900 dark:text-green-100 font-semibold mb-1">
                                                    Your WhatsApp Verification Code
                                                </p>
                                                <p className="text-xs text-green-700 dark:text-green-300">
                                                    Use this code to connect your WhatsApp number to uask.ai. Send it to the bot when you first message it.
                                                </p>
                                            </div>
                                        </div>
                                        
                                        <div className="flex items-center gap-3 bg-white dark:bg-slate-900 rounded-lg p-4 border border-green-200 dark:border-green-700">
                                            <div className="flex-1">
                                                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1 block">
                                                    Verification Code
                                                </label>
                                                <div className="font-mono text-2xl font-bold text-slate-900 dark:text-white tracking-wider">
                                                    {showWhatsappSecret ? whatsappSecret : "********"}
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => setShowWhatsappSecret(!showWhatsappSecret)}
                                                className="size-10 flex items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors"
                                            >
                                                <span className="material-symbols-outlined text-green-700 dark:text-green-300">
                                                    {showWhatsappSecret ? "visibility_off" : "visibility"}
                                                </span>
                                            </button>
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard.writeText(whatsappSecret);
                                                    pushToast({
                                                        type: "success",
                                                        title: "Copied",
                                                        message: "Code copied to clipboard.",
                                                    });
                                                }}
                                                className="size-10 flex items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors"
                                            >
                                                <span className="material-symbols-outlined text-green-700 dark:text-green-300">
                                                    content_copy
                                                </span>
                                            </button>
                                        </div>
                                        
                                        <div className="space-y-2">
                                            <p className="text-xs font-semibold text-green-900 dark:text-green-100">How to connect:</p>
                                            <ol className="text-xs text-green-800 dark:text-green-200 space-y-1 ml-4 list-decimal">
                                                <li>Save the WhatsApp bot number (ask admin for the number)</li>
                                                <li>Send a message: <code className="bg-green-200 dark:bg-green-800 px-2 py-0.5 rounded">CODE {whatsappSecret}</code></li>
                                                <li>Once verified, send math problems directly!</li>
                                                <li>You can send text questions or photos of problems</li>
                                            </ol>
                                        </div>
                                    </div>
                                    
                                    <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
                                        <div className="flex items-center gap-3">
                                            <span className="material-symbols-outlined text-slate-600 dark:text-slate-400">notifications</span>
                                            <div>
                                                <p className="text-sm font-semibold">WhatsApp Notifications</p>
                                                <p className="text-xs text-slate-500">Enable/disable WhatsApp bot responses</p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => setWhatsappEnabled(!whatsappEnabled)}
                                            className={`relative w-14 h-7 rounded-full transition-colors ${
                                                whatsappEnabled 
                                                    ? "bg-green-500" 
                                                    : "bg-slate-300 dark:bg-slate-700"
                                            }`}
                                        >
                                            <div
                                                className={`absolute top-1 left-1 size-5 bg-white rounded-full transition-transform ${
                                                    whatsappEnabled ? "translate-x-7" : "translate-x-0"
                                                }`}
                                            />
                                        </button>
                                    </div>
                                </div>

                                <div className="flex justify-end pt-4">
                                    <button
                                        onClick={handleSavePreferences}
                                        disabled={saving}
                                        className="px-8 py-3 bg-primary text-white text-sm font-bold rounded-xl hover:shadow-lg hover:bg-blue-700 transition-all disabled:opacity-50"
                                    >
                                        {saving ? "Saving..." : "Save Preferences"}
                                    </button>
                                </div>
                            </div>
                        </section>
                    )}

                    {activeTab === 'billing' && (
                        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-300">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                                <div>
                                    <h2 className="text-xl font-bold">Wallet & Programs</h2>
                                    <p className="text-slate-500 text-sm">Your credit balance and active programs.</p>
                                </div>
                                {walletSummary && (
                                    <span className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold rounded-full uppercase tracking-wider">
                                        {walletSummary.effective_tier}
                                    </span>
                                )}
                            </div>
                            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-6">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Wallet Summary</h4>
                                    <div className="space-y-4">
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium">Computed Balance</span>
                                            <span className="font-bold">{walletSummary ? walletSummary.computed_balance.toFixed(2) : "--"} credits</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium">Cached Balance</span>
                                            <span className="font-bold">{walletSummary ? walletSummary.cached_balance.toFixed(2) : "--"} credits</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium">Pending Holds</span>
                                            <span className="font-bold">{walletSummary ? walletSummary.pending_hold_credits.toFixed(2) : "--"} credits</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium">Expiring Soon</span>
                                            <span className="font-bold">{walletSummary ? walletSummary.expiring_soon_credits.toFixed(2) : "--"} credits</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                                    <div>
                                        <h4 className="text-sm font-bold mb-3">Active Programs</h4>
                                        {walletLoading ? (
                                            <p className="text-sm text-slate-500">Loading wallet programs...</p>
                                        ) : walletError ? (
                                            <p className="text-sm text-rose-500">Wallet data unavailable.</p>
                                        ) : walletPrograms.length === 0 ? (
                                            <p className="text-sm text-slate-500">No active programs.</p>
                                        ) : (
                                            <ul className="space-y-2">
                                                {walletPrograms.map((program) => (
                                                    <li key={program.id} className="text-sm text-slate-700 dark:text-slate-300">
                                                        {program.program_name || program.program_slug}
                                                        {program.next_grant_date && (
                                                            <span className="block text-[11px] text-slate-500">
                                                                Next grant: {new Date(program.next_grant_date).toLocaleDateString()}
                                                            </span>
                                                        )}
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                    <a href="/billing" className="mt-6 text-primary text-sm font-bold hover:underline text-left">Open wallet & history</a>
                                </div>
                            </div>
                        </section>
                    )}

                    {activeTab === 'security' && (
                        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-4 duration-300">
                            <div className="p-6 border-b border-slate-100 dark:border-slate-800">
                                <h2 className="text-xl font-bold">Security Settings</h2>
                                <p className="text-slate-500 text-sm">Manage your password and account protection.</p>
                            </div>
                            <div className="p-6 space-y-6">
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-bold">Current Password</label>
                                        <input className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm outline-none" type="password" placeholder="********" />
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-bold">New Password</label>
                                            <input className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm outline-none" type="password" />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-bold">Confirm New Password</label>
                                            <input className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm outline-none" type="password" />
                                        </div>
                                    </div>
                                </div>
                                <div className="flex justify-end pt-4">
                                    <button className="px-8 py-3 bg-red-600 text-white text-sm font-bold rounded-xl hover:bg-red-700 transition-all">
                                        Update Password
                                    </button>
                                </div>
                            </div>
                        </section>
                    )}
                </div>

                {/* Footer Actions */}
                <div className="flex items-center justify-between mt-12 pt-8 border-t border-slate-200 dark:border-slate-800">
                    <p className="text-sm text-slate-500 italic">Changes are saved automatically to your profile.</p>
                    <div className="flex gap-4">
                        <button className="px-6 py-3 text-sm font-bold border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">Discard</button>
                        <button className="px-10 py-3 bg-primary text-white text-sm font-bold rounded-xl hover:shadow-xl hover:bg-blue-700 transition-all">Finish</button>
                    </div>
                </div>
            </div>
        </StudentLayout>
    );
}
