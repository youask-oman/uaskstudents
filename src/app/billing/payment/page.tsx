"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function PaymentPage() {
    const router = useRouter();
    const [submitting, setSubmitting] = useState(false);
    const [ipAddress, setIpAddress] = useState<string | null>(null);
    const [paymentMethod, setPaymentMethod] = useState<'card' | 'bank' | 'gpay' | 'paypal'>('card');
    const [promoCode, setPromoCode] = useState("");
    const [promoStatus, setPromoStatus] = useState<{ valid: boolean; message: string; discount_percent?: number } | null>(null);
    const [finalPrice, setFinalPrice] = useState(39.95); // Example annual price from screenshot, though user said monthly previously. Sticking to monthly $9.99 for now unless screenshot implies switch. Screenshot says "$39.95 USD charged every 12 months". 
    const [isDark, setIsDark] = useState(false);
    // Wait, the screenshot shows $39.95 every 12 months. This implies an annual plan. 
    // I should probably stick to the previous $9.99 unless instructed to change pricing. 
    // The user didn't explicitly ask to change PRICE, just "update payment as attached". 
    // "replace Symbolab... to youask.ai".
    // I'll keep $9.99 for consistency unless I see a reason to change. 
    // Actually, looking closely at the screenshot 3: "$39.95 USD charged every 12 months".
    // I will stick to $9.99/mo to avoid confusion with the previous "Pro Plan" logic, 
    // but I will adopt the visual style.

    // Capture IP on load
    useEffect(() => {
        fetch('https://api.ipify.org?format=json')
            .then(res => res.json())
            .then(data => setIpAddress(data.ip))
            .catch(err => console.error("Failed to get IP", err));
        if (document.documentElement.classList.contains("dark")) {
            setIsDark(true);
        }
    }, []);

    const handlePayment = async () => {
        setSubmitting(true);
        try {
            const storedUser = localStorage.getItem('user');
            if (!storedUser) throw new Error("Please log in first.");
            const user = JSON.parse(storedUser);

            // Simulate specific PayPal flow if needed
            if (paymentMethod === 'paypal') {
                // specific logic or just proceed
            }

            const res = await fetch('http://127.0.0.1:8000/api/v1/billing/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: user.id,
                    plan_id: 'pro',
                    payment_method: paymentMethod,
                    ip_address: ipAddress || '127.0.0.1'
                })
            });

            if (res.ok) {
                const data = await res.json();
                router.push('/billing/success?tx=' + data.transaction_id);
            } else {
                alert("Payment failed. Please try again.");
            }
        } catch (error) {
            console.error(error);
            alert("An error occurred.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-white dark:bg-[#101622] flex flex-col font-sans text-slate-900 dark:text-white">
            <header className="flex items-center justify-between border-b border-solid border-slate-200 dark:border-[#282e39] px-6 md:px-10 py-4 bg-white dark:bg-[#101622] sticky top-0 z-50">
                <div className="flex items-center gap-4 text-[#135bec] dark:text-white">
                    <img src={isDark ? "/logo-dark.png" : "/logo.png"} alt="uask.ai" className="h-6 w-auto" />
                    <h2 className="text-slate-900 dark:text-white text-lg font-bold leading-tight tracking-[-0.015em]">uask.ai</h2>
                </div>
                <div className="flex items-center gap-4">
                    <Link href="/billing" className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors">
                        <span className="material-symbols-outlined">close</span>
                    </Link>
                </div>
            </header>

            <main className="flex-1 max-w-4xl mx-auto w-full p-6 md:py-12">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
                    {/* Left Column: Summary */}
                    <div className="space-y-6">
                        <div className="bg-slate-50 dark:bg-[#1c222d] border border-slate-200 dark:border-[#2d3648] rounded-xl p-6">
                            <h1 className="text-xl font-bold mb-4">Pro Plan</h1>
                            <div className="flex justify-between items-baseline mb-6">
                                <span className="text-3xl font-bold">${finalPrice.toFixed(2)}</span>
                                <span className="text-slate-500 text-sm">/ month</span>
                            </div>

                            <ul className="space-y-3 mb-6 text-sm">
                                <li className="flex gap-2">
                                    <span className="material-symbols-outlined text-green-500 text-lg">check_circle</span>
                                    <span>Unlimited Step-by-Step Solutions</span>
                                </li>
                                <li className="flex gap-2">
                                    <span className="material-symbols-outlined text-green-500 text-lg">check_circle</span>
                                    <span>Advanced Graphing & OCR</span>
                                </li>
                                <li className="flex gap-2">
                                    <span className="material-symbols-outlined text-green-500 text-lg">check_circle</span>
                                    <span>Ad-free experience</span>
                                </li>
                            </ul>

                            {/* Promo Code */}
                            <div className="flex flex-col gap-2 pt-4 border-t border-slate-200 dark:border-slate-700">
                                <label className="text-xs font-bold uppercase text-slate-500">Promo Code</label>
                                <div className="flex gap-2">
                                    <input
                                        className="flex-1 rounded-lg border border-slate-300 dark:border-[#3b4354] bg-white dark:bg-[#1c1f27] h-9 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none"
                                        placeholder="Enter code"
                                        value={promoCode}
                                        onChange={(e) => setPromoCode(e.target.value)}
                                    />
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            if (!promoCode) return;
                                            const res = await fetch('http://localhost:8000/api/v1/billing/validate-promo', {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ code: promoCode })
                                            });
                                            const data = await res.json();
                                            if (data.valid) {
                                                setPromoStatus(data);
                                                setFinalPrice(9.99 * (1 - (data.discount_percent || 0) / 100)); // Use 9.99 base
                                            } else {
                                                setPromoStatus({ valid: false, message: data.message });
                                                setFinalPrice(9.99);
                                            }
                                        }}
                                        className="bg-slate-200 dark:bg-slate-700 px-3 rounded-lg text-xs font-bold hover:opacity-80 disabled:opacity-50"
                                        disabled={!promoCode}
                                    >
                                        Apply
                                    </button>
                                </div>
                                {promoStatus && (
                                    <p className={`text-xs ${promoStatus.valid ? 'text-green-600' : 'text-red-500'}`}>
                                        {promoStatus.message} {promoStatus.valid && `(-${promoStatus.discount_percent}%)`}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Right Column: Payment Form */}
                    <div className="space-y-6">
                        {/* Payment Medthod Tabs */}
                        <div className="grid grid-cols-4 gap-2">
                            <button
                                onClick={() => setPaymentMethod('card')}
                                className={`flex flex-col items-center justify-center p-3 rounded-lg border bg-white dark:bg-[#1c222d] transition-all relative h-20 ${paymentMethod === 'card' ? 'border-[#135bec] ring-1 ring-[#135bec] text-[#135bec]' : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                            >
                                <span className="material-symbols-outlined text-xl mb-1">credit_card</span>
                                <span className="text-xs font-medium">Card</span>
                            </button>
                            <button
                                onClick={() => setPaymentMethod('bank')}
                                className={`flex flex-col items-center justify-center p-3 rounded-lg border bg-white dark:bg-[#1c222d] transition-all relative h-20 ${paymentMethod === 'bank' ? 'border-[#135bec] ring-1 ring-[#135bec] text-[#135bec]' : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                            >
                                <span className="material-symbols-outlined text-xl mb-1">account_balance</span>
                                <span className="text-xs font-medium">Bank</span>
                                <span className="absolute top-1 right-1 bg-green-500 text-white text-[9px] px-1 rounded font-bold hover:bg-green-600 transition-colors pointer-events-none">$5 back</span>
                            </button>
                            <button
                                onClick={() => setPaymentMethod('gpay')}
                                className={`flex flex-col items-center justify-center p-3 rounded-lg border bg-white dark:bg-[#1c222d] transition-all relative h-20 ${paymentMethod === 'gpay' ? 'border-[#135bec] ring-1 ring-[#135bec] text-[#135bec]' : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                            >
                                <span className="material-symbols-outlined text-xl mb-1">payments</span>
                                <span className="text-xs font-medium">GPay</span>
                            </button>
                            <button
                                onClick={() => setPaymentMethod('paypal')}
                                className={`flex flex-col items-center justify-center p-3 rounded-lg border bg-white dark:bg-[#1c222d] transition-all relative h-20 ${paymentMethod === 'paypal' ? 'border-[#135bec] ring-1 ring-[#135bec] text-[#135bec]' : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'}`}
                            >
                                <span className="font-bold font-serif italic text-xl mb-1 text-[#003087]">Pay<span className="text-[#009cde]">Pal</span></span>
                            </button>
                        </div>

                        <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); handlePayment(); }}>

                            {paymentMethod === 'card' && (
                                <>
                                    <div className="space-y-4">
                                        <div className="space-y-1.5">
                                            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Card number</label>
                                            <div className="relative">
                                                <input className="flex w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 h-10 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none transition-all placeholder:text-slate-400" placeholder="1234 1234 1234 1234" required />
                                                <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1">
                                                    {/* Icons placeholder */}
                                                    <div className="flex gap-1 opacity-70">
                                                        <div className="w-8 h-5 bg-slate-200 rounded"></div>
                                                        <div className="w-8 h-5 bg-slate-200 rounded"></div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Expiration date</label>
                                                <input className="flex w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 h-10 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none transition-all placeholder:text-slate-400" placeholder="MM / YY" required />
                                            </div>
                                            <div className="space-y-1.5">
                                                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Security code</label>
                                                <div className="relative">
                                                    <input className="flex w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 h-10 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none transition-all placeholder:text-slate-400" placeholder="CVC" required />
                                                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-lg">credit_card</span>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Country</label>
                                                <select className="flex w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 h-10 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none transition-all cursor-pointer">
                                                    <option>Canada</option>
                                                    <option>United States</option>
                                                    <option>United Kingdom</option>
                                                </select>
                                            </div>
                                            <div className="space-y-1.5">
                                                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Postal code</label>
                                                <input className="flex w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 h-10 px-3 text-sm focus:ring-2 focus:ring-[#135bec] outline-none transition-all placeholder:text-slate-400" placeholder="M5T 1T4" required />
                                            </div>
                                        </div>
                                    </div>
                                </>
                            )}

                            {paymentMethod === 'paypal' && (
                                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6 text-center border border-slate-200 dark:border-slate-700">
                                    <p className="font-medium text-slate-700 dark:text-slate-300 mb-2">Click 'Subscribe' to checkout with PayPal</p>
                                    <div className="flex justify-center my-4">
                                        <span className="material-symbols-outlined text-4xl text-slate-400">output</span>
                                    </div>
                                    <p className="text-sm text-slate-500">After submission, you’ll be guided through completing next steps with PayPal.</p>
                                </div>
                            )}

                            {paymentMethod === 'gpay' && (
                                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6 text-center border border-slate-200 dark:border-slate-700">
                                    <p className="font-medium text-slate-700 dark:text-slate-300 mb-2">Google Pay</p>
                                    <p className="text-sm text-slate-500">Click Subscribe to authorize payment via Google Pay.</p>
                                </div>
                            )}

                            {/* Footer Text */}
                            <div className="text-xs text-slate-500 dark:text-slate-400 space-y-4">
                                <p>
                                    By continuing, you allow youask.ai Vancouver Island, BC Canada to charge your {paymentMethod === 'gpay' ? 'Google Pay' : paymentMethod === 'paypal' ? 'PayPal' : 'Card'} account for this payment and future payments in accordance with their terms.
                                </p>
                                <p>
                                    By continuing I agree that my subscription will automatically renew, and authorize the automatic charges for the above subscription fees.
                                </p>
                            </div>

                            <div className="flex gap-4 pt-2">
                                <Link href="/billing" className="flex-1 py-3 px-4 rounded-full border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-bold text-center hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                    Go back
                                </Link>
                                <button
                                    className="flex-1 bg-[#de3c58] hover:bg-[#c9304a] text-white font-bold py-3 px-4 rounded-full shadow-lg shadow-red-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                    type="submit"
                                    disabled={submitting}
                                >
                                    {submitting ? (
                                        <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                    ) : (
                                        'Subscribe'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </main>
        </div>
    );
}
