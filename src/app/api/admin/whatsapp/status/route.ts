import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9000";
const FALLBACK_BACKEND_URL = process.env.NEXT_PUBLIC_API_FALLBACK_URL || process.env.API_BACKEND_BASE_URL || `http://orchestrator:${process.env.API_BACKEND_PORT || "9000"}`;

export async function GET() {
    try {
        const urls = [BACKEND_URL, FALLBACK_BACKEND_URL].filter(Boolean);
        let lastError: unknown = null;

        for (const baseUrl of urls) {
            try {
                const response = await fetch(`${baseUrl}/api/v1/admin/whatsapp/status`, {
                    method: "GET",
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
        console.error("Error fetching WhatsApp status:", error);
        return NextResponse.json(
            { error: "Failed to fetch WhatsApp status" },
            { status: 500 }
        );
    }
}
