"use client";

import Image from "next/image";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface AuthResponse {
    access_token: string;
    user_id: number;
    full_name: string;
    role: string;
    avatar_url?: string;
    session_token?: string;
}

export default function SignupPage() {
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [academicLevel, setAcademicLevel] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);
    const [legalAccepted, setLegalAccepted] = useState(false);
    const [isDark, setIsDark] = useState(false);
    const router = useRouter();

    useEffect(() => {
        if (document.documentElement.classList.contains("dark")) {
            setIsDark(true);
        }
    }, []);

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
            // Step 1: Create account
            const signupResponse = await fetch(`${apiBaseUrl}/api/v1/signup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    full_name: fullName,
                    email,
                    password,
                    academic_level: academicLevel,
                    terms_accepted: legalAccepted,
                    privacy_acknowledged: legalAccepted
                }),
            });

            if (!signupResponse.ok) {
                const data = await signupResponse.json();
                throw new Error(data.detail || "Signup failed");
            }

            // Step 2: Auto-login after successful signup
            const loginResponse = await fetch(`${apiBaseUrl}/api/v1/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            if (loginResponse.ok) {
                const loginData = (await loginResponse.json()) as AuthResponse;

                // Store Auth Data
                localStorage.setItem("token", loginData.access_token);
                localStorage.setItem("user_id", loginData.user_id.toString());
                localStorage.setItem("user_name", loginData.full_name);
                localStorage.setItem("user_role", loginData.role);
                localStorage.setItem("user_avatar", loginData.avatar_url || "");
                localStorage.setItem("user", JSON.stringify(loginData));

                // Redirect new users to onboarding to set their location
                router.push("/onboarding");
            } else {
                // If auto-login fails, show success message and redirect to login
                setSuccess(true);
            }

        } catch (err) {
            const message = err instanceof Error ? err.message : "Signup failed";
            setError(message);
        } finally {
            setLoading(false);
        }
    };
    return (
        <div className="font-display bg-background-light dark:bg-background-dark min-h-screen text-[#111318] dark:text-white transition-colors duration-200 flex flex-col">
            {/* Top Navigation Bar */}
            <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-gray-200 dark:border-gray-800 px-6 py-4 md:px-10 bg-white dark:bg-background-dark">
                <Link href="/" className="flex items-center gap-3">
                    <Image
                        src={isDark ? "/logo-dark.png" : "/logo.png"}
                        alt="uask.ai"
                        width={96}
                        height={24}
                        className="h-8 w-auto"
                        priority
                    />
                    <h2 className="text-[#111318] dark:text-white text-xl font-bold leading-tight tracking-tight">uask.ai</h2>
                </Link>
                <div className="flex items-center gap-4">
                    <span className="hidden md:inline text-sm text-gray-500 dark:text-gray-400">Already have an account?</span>
                    <Link href="/login">
                        <button className="flex min-w-[84px] cursor-pointer items-center justify-center rounded-lg h-10 px-6 bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-sm font-bold leading-normal">
                            <span>Log in</span>
                        </button>
                    </Link>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center p-6 md:p-12">
                <div className="w-full max-w-[540px] bg-white dark:bg-[#1a2130] rounded-xl shadow-xl border border-gray-100 dark:border-gray-800 overflow-hidden">
                    <div className="p-8 md:p-12">
                        {/* Heading & Subtext */}
                        <div className="text-center mb-8">
                            <h1 className="text-[#111318] dark:text-white text-3xl font-extrabold tracking-tight mb-2">Start Your Learning Journey</h1>
                            <p className="text-gray-500 dark:text-gray-400 text-base">Empowering your Math & Physics journey with AI</p>
                        </div>

                        {success ? (
                            <div className="text-center py-8">
                                <div className="mx-auto w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-4">
                                    <span className="material-symbols-outlined text-green-600 dark:text-green-400 text-3xl">mark_email_read</span>
                                </div>
                                <h3 className="text-xl font-bold text-[#111318] dark:text-white mb-2">Check your email</h3>
                                <p className="text-gray-600 dark:text-gray-400 mb-6">
                                    We have sent a verification link to <strong>{email}</strong>. Please click the link to verify your account and log in.
                                </p>
                                <Link href="/login">
                                    <button className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3 rounded-lg transition-colors">
                                        Return to Login
                                    </button>
                                </Link>
                            </div>
                        ) : (
                            <>

                                {/* Error Message */}
                                {error && (
                                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-sm text-center font-medium">
                                        {error}
                                    </div>
                                )}

                                {/* Registration Form */}
                                <form className="space-y-5" onSubmit={handleSignup}>
                                    {/* Full Name */}
                                    <label className="block">
                                        <p className="text-[#111318] dark:text-gray-200 text-sm font-semibold mb-2">Full Name</p>
                                        <div className="relative">
                                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">person</span>
                                            <input
                                                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-primary/20 focus:border-primary py-3.5 pl-11 pr-4 text-[#111318] dark:text-white transition-all outline-none placeholder:text-gray-400"
                                                placeholder="Enter your full name"
                                                type="text"
                                                value={fullName}
                                                onChange={(e) => setFullName(e.target.value)}
                                                required
                                            />
                                        </div>
                                    </label>

                                    {/* Email Address */}
                                    <label className="block">
                                        <p className="text-[#111318] dark:text-gray-200 text-sm font-semibold mb-2">Email Address</p>
                                        <div className="relative">
                                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">mail</span>
                                            <input
                                                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-primary/20 focus:border-primary py-3.5 pl-11 pr-4 text-[#111318] dark:text-white transition-all outline-none placeholder:text-gray-400"
                                                placeholder="student@university.edu"
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                required
                                            />
                                        </div>
                                    </label>

                                    {/* Academic Level */}
                                    <label className="block">
                                        <p className="text-[#111318] dark:text-gray-200 text-sm font-semibold mb-2">Academic Level</p>
                                        <div className="relative">
                                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">school</span>
                                            <select
                                                className="w-full appearance-none rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-primary/20 focus:border-primary py-3.5 pl-11 pr-10 text-[#111318] dark:text-white transition-all outline-none"
                                                value={academicLevel}
                                                onChange={(e) => setAcademicLevel(e.target.value)}
                                                required
                                            >
                                                <option disabled value="">Select your level</option>
                                                <option value="middle">Middle School</option>
                                                <option value="high">High School</option>
                                                <option value="college">College / University</option>
                                                <option value="advanced">Advanced Research</option>
                                            </select>
                                            <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">expand_more</span>
                                        </div>
                                    </label>

                                    {/* Password */}
                                    <label className="block">
                                        <p className="text-[#111318] dark:text-gray-200 text-sm font-semibold mb-2">Password</p>
                                        <div className="relative">
                                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">lock</span>
                                            <input
                                                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:ring-2 focus:ring-primary/20 focus:border-primary py-3.5 pl-11 pr-4 text-[#111318] dark:text-white transition-all outline-none placeholder:text-gray-400"
                                                placeholder="Create a strong password"
                                                type="password"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                required
                                            />
                                        </div>
                                    </label>

                                    {/* Terms */}
                                    <label className="flex items-start gap-3 cursor-pointer pt-2">
                                        <div className="mt-1">
                                            <input
                                                className="w-5 h-5 rounded border-gray-300 dark:border-gray-700 text-primary focus:ring-primary/30"
                                                type="checkbox"
                                                checked={legalAccepted}
                                                onChange={(e) => setLegalAccepted(e.target.checked)}
                                                required
                                            />
                                        </div>
                                        <span className="text-sm text-gray-600 dark:text-gray-400 leading-tight">
                                            By creating an account, you agree to the <a className="text-primary font-bold hover:underline" href="/legal/terms">Terms of Service</a> and acknowledge the <a className="text-primary font-bold hover:underline" href="/legal/privacy">Privacy Policy</a>.
                                        </span>
                                    </label>

                                    {/* Submit Button */}
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="w-full flex items-center justify-center h-14 bg-primary hover:bg-blue-700 text-white text-base font-bold rounded-lg shadow-lg shadow-primary/20 transition-all mt-4 disabled:opacity-70 disabled:cursor-not-allowed"
                                    >
                                        {loading ? (
                                            <span className="size-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                        ) : (
                                            <span>Create Account</span>
                                        )}
                                    </button>
                                </form>
                            </>
                        )}
                    </div>

                    {/* Footer / Login link mobile */}
                    <div className="bg-gray-50 dark:bg-black/20 p-6 text-center border-t border-gray-100 dark:border-gray-800">
                        <p className="text-gray-600 dark:text-gray-400 text-sm">
                            Existing user? <Link className="text-primary font-bold hover:underline" href="/login">Log in to your account</Link>
                        </p>
                    </div>
                </div>
            </main>

            {/* Footer Credits */}
            <footer className="py-6 text-center text-gray-400 dark:text-gray-600 text-xs">
                © 2023 uask.ai. All rights reserved. Designed for the next generation of scientists.
            </footer>
        </div>
    );
}
