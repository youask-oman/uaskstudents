"use client";

import Image from "next/image";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface SchoolSearchResult {
    id: number;
    school_name: string;
    city: string | null;
    district: string | null;
}

export default function OnboardingPage() {
    const router = useRouter();
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

    // Form state
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

    // UI state
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [userName, setUserName] = useState("");
    const [isDark, setIsDark] = useState(false);

    useEffect(() => {
        // Check if user is logged in
        const userId = localStorage.getItem("user_id");
        const name = localStorage.getItem("user_name");
        if (!userId) {
            router.push("/login");
            return;
        }
        setUserName(name || "Student");

        // Check dark mode
        if (document.documentElement.classList.contains("dark")) {
            setIsDark(true);
        }

        // Fetch grade levels
        fetch(`${apiBaseUrl}/api/v1/locations/grades`)
            .then(res => res.json())
            .then(data => setGrades(data.grades || []))
            .catch(console.error);
    }, [apiBaseUrl, router]);

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
            })
            .catch(console.error);
    }, [profileCountry, apiBaseUrl]);

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
                .catch(() => setSchoolSearching(false));
        }, 300);

        return () => clearTimeout(timer);
    }, [schoolQuery, profileCountry, profileProvinceState, apiBaseUrl]);

    const handleSelectSchool = (school: SchoolSearchResult) => {
        setSchoolId(school.id);
        setSelectedSchoolName(school.school_name);
        setSchoolQuery(school.school_name);
        setShowSchoolDropdown(false);
    };

    const handleSubmit = async () => {
        if (!profileCountry || !profileProvinceState || !gradeLevel) {
            setError("Please fill in all required fields.");
            return;
        }

        setSaving(true);
        setError("");

        const userId = localStorage.getItem("user_id");

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
                // Mark onboarding as complete
                localStorage.setItem("onboarding_complete", "true");
                // Redirect to dashboard
                router.push("/dashboard");
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to save profile.");
            }
        } catch {
            setError("Something went wrong. Please try again.");
        } finally {
            setSaving(false);
        }
    };

    const handleSkip = () => {
        localStorage.setItem("onboarding_complete", "skipped");
        router.push("/dashboard");
    };

    return (
        <div className="font-display bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 min-h-screen text-[#111318] dark:text-white flex flex-col">
            {/* Header */}
            <header className="flex items-center justify-between px-6 py-4 md:px-10">
                <Link href="/" className="flex items-center gap-3">
                    <Image
                        src={isDark ? "/logo-dark.png" : "/logo.png"}
                        alt="uask.ai"
                        width={96}
                        height={24}
                        className="h-8 w-auto"
                        priority
                    />
                    <h2 className="text-[#111318] dark:text-white text-xl font-bold tracking-tight">uask.ai</h2>
                </Link>
            </header>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center p-6 md:p-12">
                <div className="w-full max-w-2xl">
                    {/* Welcome Card */}
                    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-2xl border border-gray-100 dark:border-slate-700 overflow-hidden">
                        {/* Header Section */}
                        <div className="bg-gradient-to-r from-primary to-blue-600 p-8 text-white text-center">
                            <div className="size-20 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                                <span className="material-symbols-outlined text-4xl">waving_hand</span>
                            </div>
                            <h1 className="text-3xl font-black mb-2">Welcome, {userName}!</h1>
                            <p className="text-blue-100 text-lg">Let&apos;s personalize your learning experience</p>
                        </div>

                        {/* Form Section */}
                        <div className="p-8">
                            {/* Why This Matters */}
                            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-6 flex gap-3">
                                <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 shrink-0">lightbulb</span>
                                <div>
                                    <p className="text-sm text-amber-800 dark:text-amber-200 font-medium">
                                        Your AI tutor adapts to your curriculum!
                                    </p>
                                    <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                                        Students in Ontario learn different math topics than those in Texas.
                                        We&apos;ll use the right terminology and methods for your location.
                                    </p>
                                </div>
                            </div>

                            {error && (
                                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-3 mb-4 text-red-700 dark:text-red-300 text-sm">
                                    {error}
                                </div>
                            )}

                            <div className="space-y-5">
                                {/* Country */}
                                <div>
                                    <label className="block text-sm font-bold mb-2">
                                        Where do you go to school? <span className="text-red-500">*</span>
                                    </label>
                                    <div className="grid grid-cols-2 gap-3">
                                        {[
                                            { value: 'USA', label: '🇺🇸 United States', icon: 'flag' },
                                            { value: 'Canada', label: '🇨🇦 Canada', icon: 'flag' }
                                        ].map(country => (
                                            <button
                                                key={country.value}
                                                onClick={() => {
                                                    setProfileCountry(country.value);
                                                    setProfileProvinceState("");
                                                    setSchoolId(null);
                                                    setSelectedSchoolName("");
                                                    setSchoolQuery("");
                                                }}
                                                className={`p-4 rounded-xl border-2 text-left transition-all ${profileCountry === country.value
                                                        ? 'border-primary bg-primary/5 ring-4 ring-primary/10'
                                                        : 'border-gray-200 dark:border-slate-600 hover:border-primary/50'
                                                    }`}
                                            >
                                                <span className="text-2xl">{country.label.slice(0, 4)}</span>
                                                <p className="font-bold mt-1">{country.label.slice(5)}</p>
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Province/State */}
                                <div>
                                    <label className="block text-sm font-bold mb-2">
                                        {provinceLabel} <span className="text-red-500">*</span>
                                    </label>
                                    <select
                                        value={profileProvinceState}
                                        onChange={(e) => {
                                            setProfileProvinceState(e.target.value);
                                            setSchoolId(null);
                                            setSelectedSchoolName("");
                                            setSchoolQuery("");
                                        }}
                                        disabled={!profileCountry}
                                        className="w-full bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-xl h-12 px-4 text-sm focus:ring-2 focus:ring-primary outline-none appearance-none disabled:opacity-50"
                                    >
                                        <option value="">Select {provinceLabel.toLowerCase()}...</option>
                                        {provinces.map(p => (
                                            <option key={p} value={p}>{p}</option>
                                        ))}
                                    </select>
                                </div>

                                {/* Grade Level */}
                                <div>
                                    <label className="block text-sm font-bold mb-2">
                                        What grade are you in? <span className="text-red-500">*</span>
                                    </label>
                                    <div className="grid grid-cols-4 gap-2">
                                        {grades.map(g => (
                                            <button
                                                key={g}
                                                onClick={() => setGradeLevel(g)}
                                                className={`p-3 rounded-lg border-2 text-sm font-bold transition-all ${gradeLevel === g
                                                        ? 'border-primary bg-primary text-white'
                                                        : 'border-gray-200 dark:border-slate-600 hover:border-primary/50'
                                                    }`}
                                            >
                                                {g.replace('Grade ', '')}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* School Search (Optional) */}
                                <div className="relative">
                                    <label className="block text-sm font-bold mb-2">
                                        Your School <span className="text-gray-400 font-normal">(optional)</span>
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
                                            placeholder={profileCountry && profileProvinceState ? "Start typing your school name..." : "Select country and province first"}
                                            disabled={!profileCountry || !profileProvinceState}
                                            className="w-full bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-xl h-12 px-4 pr-10 text-sm focus:ring-2 focus:ring-primary outline-none disabled:opacity-50"
                                        />
                                        {schoolSearching && (
                                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Dropdown */}
                                    {showSchoolDropdown && schoolResults.length > 0 && (
                                        <div className="absolute z-50 w-full mt-1 bg-white dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                                            {schoolResults.map(school => (
                                                <button
                                                    key={school.id}
                                                    onClick={() => handleSelectSchool(school)}
                                                    className="w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-slate-600 border-b border-gray-100 dark:border-slate-600 last:border-0"
                                                >
                                                    <p className="text-sm font-medium truncate">{school.school_name}</p>
                                                    {school.city && <p className="text-xs text-gray-500">{school.city}</p>}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Selected School Badge */}
                                {schoolId && selectedSchoolName && (
                                    <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                                        <span className="material-symbols-outlined text-green-600">verified</span>
                                        <span className="text-sm text-green-700 dark:text-green-300 font-medium truncate">
                                            {selectedSchoolName}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-100 dark:border-slate-700">
                                <button
                                    onClick={handleSkip}
                                    className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 text-sm font-medium transition-colors"
                                >
                                    Skip for now →
                                </button>
                                <button
                                    onClick={handleSubmit}
                                    disabled={saving || !profileCountry || !profileProvinceState || !gradeLevel}
                                    className="px-8 py-3 bg-primary hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                >
                                    {saving ? (
                                        <>
                                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            Start Learning
                                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
