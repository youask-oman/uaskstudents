"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { API_BASE_URL } from "@/lib/api";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "qr_ready";

interface WhatsAppBotState {
    status: ConnectionStatus;
    qrCode?: string;
    phoneNumber?: string;
    messagesCount?: number;
    lastMessageAt?: string;
    error?: string;
}

export default function WhatsAppBotPage() {
    const [botState, setBotState] = useState<WhatsAppBotState>({
        status: "disconnected",
    });
    const [isLoading, setIsLoading] = useState(false);

    const fetchBotStatus = async () => {
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const response = await fetch(`${API_BASE_URL}/api/admin/whatsapp/status`, {
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (response.ok) {
                const data = await response.json();
                setBotState(data);
            }
        } catch (error) {
            console.error("Failed to fetch bot status:", error);
        }
    };

    const initializeBot = async () => {
        setIsLoading(true);
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const response = await fetch(`${API_BASE_URL}/api/admin/whatsapp/initialize`, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (response.ok) {
                const data = await response.json();
                setBotState(data);
            } else {
                const errorData = await response.json();
                setBotState((prev) => ({
                    ...prev,
                    error: errorData.error || errorData.message || "Failed to initialize bot",
                }));
            }
        } catch (error) {
            console.error("Failed to initialize bot:", error);
            setBotState((prev) => ({
                ...prev,
                error: "Failed to connect to backend",
            }));
        } finally {
            setIsLoading(false);
        }
    };

    const disconnectBot = async () => {
        setIsLoading(true);
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
            const response = await fetch(`${API_BASE_URL}/api/admin/whatsapp/disconnect`, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            });
            if (response.ok) {
                setBotState({ status: "disconnected" });
            }
        } catch (error) {
            console.error("Failed to disconnect bot:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchBotStatus();
        const interval = setInterval(fetchBotStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    const getStatusBadge = () => {
        const statusConfig = {
            disconnected: { color: "bg-gray-500", text: "Disconnected", icon: "power_settings_new" },
            connecting: { color: "bg-yellow-500", text: "Connecting...", icon: "sync" },
            qr_ready: { color: "bg-blue-500", text: "Scan QR Code", icon: "qr_code_scanner" },
            connected: { color: "bg-green-500", text: "Connected", icon: "check_circle" },
        };

        const config = statusConfig[botState.status];
        return (
            <div className={`${config.color} text-white px-4 py-2 rounded-lg flex items-center gap-2 shadow-lg`}>
                <span className="material-symbols-outlined text-lg animate-pulse">{config.icon}</span>
                <span className="font-semibold">{config.text}</span>
            </div>
        );
    };

    return (
        <div className="p-8 max-w-6xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className="size-14 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center shadow-lg">
                        <span className="material-symbols-outlined text-white text-3xl">chat</span>
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">WhatsApp Bot</h1>
                        <p className="text-slate-600 dark:text-slate-400 mt-1">
                            Manage your WhatsApp AI tutor bot connection
                        </p>
                    </div>
                </div>
                {getStatusBadge()}
            </div>

            {/* Error Alert */}
            {botState.error && (
                <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
                    <span className="material-symbols-outlined text-red-600 dark:text-red-400">error</span>
                    <div className="flex-1">
                        <h3 className="font-semibold text-red-900 dark:text-red-200">Error</h3>
                        <p className="text-red-700 dark:text-red-300 text-sm mt-1">{botState.error}</p>
                    </div>
                </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Connection Card */}
                <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 shadow-sm">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                        <span className="material-symbols-outlined">settings_phone</span>
                        Connection
                    </h2>

                    {botState.status === "disconnected" && (
                        <div className="space-y-4">
                            <p className="text-slate-600 dark:text-slate-400">
                                Connect a WhatsApp number to enable the AI tutor bot. Students will be able to send
                                math questions via WhatsApp and receive instant solutions.
                            </p>
                            <button
                                onClick={initializeBot}
                                disabled={isLoading}
                                className="w-full py-3 bg-green-500 hover:bg-green-600 text-white rounded-lg font-semibold transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                <span className="material-symbols-outlined">qr_code_scanner</span>
                                Initialize Connection
                            </button>
                        </div>
                    )}

                    {botState.status === "connecting" && (
                        <div className="flex flex-col items-center justify-center py-8">
                            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-green-500 mb-4"></div>
                            <p className="text-slate-600 dark:text-slate-400">Initializing WhatsApp connection...</p>
                        </div>
                    )}

                    {botState.status === "qr_ready" && botState.qrCode && (
                        <div className="space-y-4">
                            <div className="bg-slate-50 dark:bg-slate-900 p-4 rounded-lg">
                                <div className="flex justify-center mb-4">
                                    <Image
                                        src={botState.qrCode}
                                        alt="WhatsApp QR Code"
                                        width={256}
                                        height={256}
                                        className="border-4 border-slate-200 dark:border-slate-700 rounded-lg"
                                    />
                                </div>
                                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                                    <p className="font-semibold text-slate-900 dark:text-white">Scan this QR code:</p>
                                    <ol className="list-decimal list-inside space-y-1 ml-2">
                                        <li>Open WhatsApp on your phone</li>
                                        <li>Go to Settings → Linked Devices</li>
                                        <li>Tap &quot;Link a Device&quot;</li>
                                        <li>Scan this QR code</li>
                                    </ol>
                                </div>
                            </div>
                            <button
                                onClick={disconnectBot}
                                className="w-full py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-semibold transition-all"
                            >
                                Cancel
                            </button>
                        </div>
                    )}

                    {botState.status === "connected" && (
                        <div className="space-y-4">
                            <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-800">
                                <div className="flex items-center gap-3 mb-3">
                                    <span className="material-symbols-outlined text-green-600 dark:text-green-400">check_circle</span>
                                    <span className="font-semibold text-green-900 dark:text-green-200">Bot is Active</span>
                                </div>
                                {botState.phoneNumber && (
                                    <p className="text-green-700 dark:text-green-300 text-sm">
                                        Connected: {botState.phoneNumber}
                                    </p>
                                )}
                            </div>
                            <button
                                onClick={disconnectBot}
                                disabled={isLoading}
                                className="w-full py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                <span className="material-symbols-outlined">power_settings_new</span>
                                Disconnect Bot
                            </button>
                        </div>
                    )}
                </div>

                {/* Statistics Card */}
                <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 shadow-sm">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                        <span className="material-symbols-outlined">analytics</span>
                        Statistics
                    </h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-900 rounded-lg">
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-blue-500">chat</span>
                                <span className="text-slate-700 dark:text-slate-300">Total Messages</span>
                            </div>
                            <span className="text-2xl font-bold text-slate-900 dark:text-white">
                                {botState.messagesCount || 0}
                            </span>
                        </div>

                        <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-900 rounded-lg">
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-purple-500">schedule</span>
                                <span className="text-slate-700 dark:text-slate-300">Last Message</span>
                            </div>
                            <span className="text-sm font-semibold text-slate-900 dark:text-white">
                                {botState.lastMessageAt || "N/A"}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Info Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold text-blue-900 dark:text-blue-200 mb-3 flex items-center gap-2">
                        <span className="material-symbols-outlined">info</span>
                        How It Works
                    </h3>
                    <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-300">
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">check</span>
                            <span>Students send math problems via WhatsApp</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">check</span>
                            <span>AI tutor processes and solves the problem</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">check</span>
                            <span>Step-by-step solution sent back instantly</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">check</span>
                            <span>Supports text and photo-based questions</span>
                        </li>
                    </ul>
                </div>

                <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold text-amber-900 dark:text-amber-200 mb-3 flex items-center gap-2">
                        <span className="material-symbols-outlined">security</span>
                        Security
                    </h3>
                    <ul className="space-y-2 text-sm text-amber-800 dark:text-amber-300">
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">lock</span>
                            <span>Each student has a unique WhatsApp secret code</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">lock</span>
                            <span>Bot verifies credit/program eligibility before responding</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">lock</span>
                            <span>Code required on first message from new number</span>
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-xs mt-0.5">lock</span>
                            <span>Students can view code in Settings → Preferences</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
}
