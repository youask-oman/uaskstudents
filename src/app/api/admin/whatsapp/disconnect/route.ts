import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || "http://orchestrator:8000";

export async function POST() {
    try {
        const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
        let lastError: unknown = null;

        for (const baseUrl of urls) {
            try {
                const response = await fetch(`${baseUrl}/api/v1/admin/whatsapp/disconnect`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                });
                const data = await response.json();
                return NextResponse.json(data);
            } catch (err) {
                lastError = err;
            }
        }
        throw lastError;
    } catch (error) {
        console.error("Error disconnecting WhatsApp bot:", error);
        return NextResponse.json(
            { error: "Failed to disconnect WhatsApp bot" },
            { status: 500 }
        );
    }
}
