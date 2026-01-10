"use client";

import { useState, useEffect } from "react";
import StudentLayout from "@/components/layout/StudentLayout";

type TabId = 'profile' | 'preferences' | 'billing' | 'security';

interface ProfileData {
    id: number;
    full_name: string;
    email: string;
    academic_level: string;
    timezone: string;
    theme: string;
    preferred_language: string;
    solving_mode: string;
    subscription_tier: string;
    subscription_status: string;
    usage: {
        questions_count: number;
        questions_total: number;
        scans_count: number;
        scans_total: number;
    };
}

export default function ProfilePage() {
    const [activeTab, setActiveTab] = useState<TabId>('profile');
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Form states
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [academicLevel, setAcademicLevel] = useState("");
    const [timezone, setTimezone] = useState("");
    const [theme, setTheme] = useState("");
    const [language, setLanguage] = useState("");
    const [solvingMode, setSolvingMode] = useState("");

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;

        fetch(`http://localhost:8000/api/v1/user/profile?user_id=${userId}`)
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
                setLoading(false);
            })
            .catch(err => {
                console.error("Error fetching profile:", err);
                setLoading(false);
            });
    }, []);

    const handleSaveProfile = async () => {
        const userId = localStorage.getItem("user_id");
        setSaving(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/user/profile?user_id=${userId}`, {
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
                alert("Profile updated successfully!");
                // Update local storage if needed
                localStorage.setItem("user_name", fullName);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    const handleSavePreferences = async () => {
        const userId = localStorage.getItem("user_id");
        setSaving(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/user/preferences?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    theme: theme,
                    preferred_language: language,
                    solving_mode: solvingMode
                })
            });
            if (res.ok) {
                alert("Preferences updated!");
                // Apply theme immediately
                if (theme === 'dark') {
                    document.documentElement.classList.add('dark');
                } else if (theme === 'light') {
                    document.documentElement.classList.remove('dark');
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <StudentLayout>
                <div className="p-8 flex items-center justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
            </StudentLayout>
        );
    }

    const tabs: { id: TabId; label: string; icon: string }[] = [
        { id: 'profile', label: 'Profile', icon: 'person' },
        { id: 'preferences', label: 'Preferences', icon: 'settings' },
        { id: 'billing', label: 'Plan & Billing', icon: 'credit_card' },
        { id: 'security', label: 'Security', icon: 'shield' },
    ];

    return (
        <StudentLayout>
            <div className="max-w-4xl mx-auto py-10 px-8">
                {/* Header */}
                <div className="mb-10">
                    <h1 className="text-4xl font-black tracking-tight mb-2">Settings & Preferences</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-lg">Personalize your learning experience and manage account details.</p>
                </div>

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
                                            <option>Arabic (العربية)</option>
                                            <option>French (Français)</option>
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
                                    <h2 className="text-xl font-bold">Plan & Billing</h2>
                                    <p className="text-slate-500 text-sm">You are currently on the <span className="text-primary font-bold">{profile?.subscription_tier || "Pro Student"}</span> plan.</p>
                                </div>
                                <span className="px-3 py-1 bg-green-100 text-green-700 text-[10px] font-bold rounded-full uppercase tracking-wider">ACTIVE</span>
                            </div>
                            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-6">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Quota Usage</h4>
                                    <div className="space-y-4">
                                        <div className="space-y-1">
                                            <div className="flex justify-between text-sm">
                                                <span className="font-medium">OCR Scans (Images)</span>
                                                <span className="font-bold">{profile?.usage.scans_count || 0} / {profile?.usage.scans_total || 50}</span>
                                            </div>
                                            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                                                <div
                                                    className="bg-primary h-full transition-all duration-500"
                                                    style={{ width: `${(profile?.usage.scans_count || 0) / (profile?.usage.scans_total || 50) * 100}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                        <div className="space-y-1">
                                            <div className="flex justify-between text-sm">
                                                <span className="font-medium">Monthly Questions</span>
                                                <span className="font-bold">{profile?.usage.questions_count || 0} / {profile?.usage.questions_total || 100}</span>
                                            </div>
                                            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                                                <div
                                                    className="bg-primary h-full transition-all duration-500"
                                                    style={{ width: `${(profile?.usage.questions_count || 0) / (profile?.usage.questions_total || 100) * 100}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                                    <div>
                                        <h4 className="text-sm font-bold mb-1">Next Payment</h4>
                                        <p className="text-3xl font-black">$9.99<span className="text-sm font-normal text-slate-400"> /mo</span></p>
                                        <p className="text-xs text-slate-500 mt-2">Next billing date: Jan 24, 2026</p>
                                    </div>
                                    <button className="mt-6 text-primary text-sm font-bold hover:underline text-left">View billing history</button>
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
                                        <input className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl h-12 px-4 text-sm outline-none" type="password" placeholder="••••••••" />
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
