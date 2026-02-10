"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function RequestsPage() {
    const router = useRouter();

    useEffect(() => {
        router.replace("/adminpayments?tab=requests");
    }, [router]);

    return null;
}
