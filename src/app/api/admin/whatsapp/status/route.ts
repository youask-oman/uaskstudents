import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function GET() {
    try {
        const response = await fetch(`${BACKEND_URL}/api/v1/admin/whatsapp/status`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error("Error fetching WhatsApp status:", error);
        return NextResponse.json(
            { error: "Failed to fetch WhatsApp status" },
            { status: 500 }
        );
    }
}
