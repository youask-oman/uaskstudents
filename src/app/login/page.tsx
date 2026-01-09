"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
    const [showPassword, setShowPassword] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const response = await fetch("http://localhost:8000/api/v1/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || "Login failed");
            }

            const data = await response.json();

            // Store Auth Data
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user_id", data.user_id.toString());
            localStorage.setItem("user_name", data.full_name);
            localStorage.setItem("user_role", data.role);
            localStorage.setItem("user_avatar", data.avatar_url || "");
            localStorage.setItem("user", JSON.stringify(data));

            // Redirect
            router.push("/dashboard");

        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-background-light dark:bg-background-dark font-display min-h-screen flex flex-col relative overflow-x-hidden transition-colors duration-200">
            {/* Background Decoration */}
            <div className="fixed inset-0 z-0 bg-pattern pointer-events-none"></div>
            <div className="fixed top-0 left-0 w-full h-full z-0 pointer-events-none overflow-hidden">
                <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[120px]"></div>
                <div className="absolute -bottom-[10%] -right-[10%] w-[40%] h-[40%] rounded-full bg-primary/10 blur-[120px]"></div>
            </div>

            <div className="relative z-10 flex h-full grow flex-col">
                {/* Top Navigation */}
                <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-black/5 dark:border-white/5 px-6 md:px-10 py-4 bg-white/80 dark:bg-background-dark/80 backdrop-blur-md">
                    <Link href="/" className="flex items-center gap-3 text-[#111318] dark:text-white">
                        <div className="size-8 bg-primary rounded-lg flex items-center justify-center text-white">
                            <span className="material-symbols-outlined">functions</span>
                        </div>
                        <h2 className="text-[#111318] dark:text-white text-xl font-extrabold leading-tight tracking-[-0.015em]">uask.ai</h2>
                    </Link>
                    <div className="hidden md:block">
                        <span className="text-sm text-[#616f89] dark:text-gray-400">Master Math & Physics with AI</span>
                    </div>
                </header>

                <main className="flex-1 flex items-center justify-center px-4 py-12">
                    <div className="w-full max-w-[440px] bg-white dark:bg-[#1a212f] rounded-xl shadow-2xl shadow-primary/5 border border-black/5 dark:border-white/5 p-8 flex flex-col">
                        {/* Headline */}
                        <div className="text-center mb-8">
                            <h1 className="text-[#111318] dark:text-white text-3xl font-bold leading-tight mb-2">Welcome back</h1>
                            <p className="text-[#616f89] dark:text-gray-400 text-sm">Continue your learning journey</p>
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-sm text-center font-medium">
                                {error}
                            </div>
                        )}

                        {/* Form Section */}
                        <form className="space-y-5" onSubmit={handleLogin}>
                            {/* Email Field */}
                            <div className="flex flex-col gap-1.5">
                                <label className="text-[#111318] dark:text-white text-sm font-semibold leading-normal">Email Address</label>
                                <input
                                    className="form-input w-full rounded-lg text-[#111318] dark:text-white focus:outline-0 focus:ring-2 focus:ring-primary/20 border border-[#dbdfe6] dark:border-gray-700 bg-white dark:bg-[#101622] focus:border-primary h-12 placeholder:text-[#616f89] px-4 text-sm font-normal"
                                    placeholder="name@university.edu"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                />
                            </div>

                            {/* Password Field */}
                            <div className="flex flex-col gap-1.5">
                                <div className="flex justify-between items-center">
                                    <label className="text-[#111318] dark:text-white text-sm font-semibold leading-normal">Password</label>
                                    <a className="text-primary text-xs font-semibold hover:underline" href="#">Forgot?</a>
                                </div>
                                <div className="relative">
                                    <input
                                        className="form-input w-full rounded-lg text-[#111318] dark:text-white focus:outline-0 focus:ring-2 focus:ring-primary/20 border border-[#dbdfe6] dark:border-gray-700 bg-white dark:bg-[#101622] focus:border-primary h-12 placeholder:text-[#616f89] px-4 pr-12 text-sm font-normal"
                                        placeholder="••••••••"
                                        type={showPassword ? "text" : "password"}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                    />
                                    <button
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#616f89] hover:text-primary transition-colors"
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                    >
                                        <span className="material-symbols-outlined text-[20px]">{showPassword ? 'visibility_off' : 'visibility'}</span>
                                    </button>
                                </div>
                            </div>

                            {/* Login Button */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3.5 rounded-lg transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
                            >
                                {loading ? (
                                    <span className="size-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                ) : (
                                    <>
                                        Log In
                                        <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                                    </>
                                )}
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="relative my-8">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-[#dbdfe6] dark:border-gray-700"></div>
                            </div>
                            <div className="relative flex justify-center text-xs uppercase">
                                <span className="bg-white dark:bg-[#1a212f] px-4 text-[#616f89] dark:text-gray-400 font-medium">Or continue with</span>
                            </div>
                        </div>

                        {/* OAuth Buttons */}
                        <div className="grid grid-cols-2 gap-4">
                            <button className="flex items-center justify-center gap-2 py-3 border border-[#dbdfe6] dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors group">
                                <img alt="" className="w-5 h-5" data-alt="Google colorful icon logo" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAJWbywDH8KRd1dJJEkxXYBQ0UsO11AYQEWqePDSRvpdcYQxgbR39aHPFaq1SspnSEpJDyR30md6bK5rcnBFV0WFayiGt1FTjdk0HCY64aR4ivtOCH2eXyR7KwIumZPDpiWw7b47yeX4PEJeKJLFDE9c5M6rgP_wJ5dwdZNM7QcYB47R3CpCL_luMEqdCEUN799qAkfMqCETnzzZl-2mYwUOSKCoHRy1nNrEKQtO4pcYJ33ZDhuEvmKh8f2AoXUjUv_ckHkua-Ecl-k" />
                                <span className="text-sm font-semibold text-[#111318] dark:text-white">Google</span>
                            </button>
                            <button className="flex items-center justify-center gap-2 py-3 border border-[#dbdfe6] dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors group">
                                <span className="material-symbols-outlined text-[22px] text-[#111318] dark:text-white">ios</span>
                                <span className="text-sm font-semibold text-[#111318] dark:text-white">Apple</span>
                            </button>
                        </div>

                        {/* Footer Toggle */}
                        <div className="mt-8 text-center">
                            <p className="text-[#616f89] dark:text-gray-400 text-sm">
                                Don't have an account?
                                <Link className="text-primary font-bold hover:underline ml-1" href="/signup">Sign up</Link>
                            </p>
                        </div>
                    </div>
                </main>

                {/* Footer Copyright */}
                <footer className="py-6 px-10 text-center">
                    <p className="text-xs text-[#616f89] dark:text-gray-500">© 2024 uask.ai. All rights reserved. Physics-informed AI for education.</p>
                </footer>
            </div>
        </div>
    );
}
