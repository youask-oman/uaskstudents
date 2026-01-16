"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function HeroCTA() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);

    useEffect(() => {
        if (localStorage.getItem("token")) {
            setIsLoggedIn(true);
        }
    }, []);

    if (isLoggedIn) {
        return (
            <Link href="/solve">
                <button className="h-14 px-8 bg-primary text-white rounded-xl font-bold text-lg hover:scale-[1.02] transition-transform shadow-xl shadow-primary/25 flex items-center gap-2">
                    Go to Workspace
                    <span className="material-symbols-outlined">dashboard</span>
                </button>
            </Link>
        );
    }

    return (
        <Link href="/signup">
            <button className="h-14 px-8 bg-primary text-white rounded-xl font-bold text-lg hover:scale-[1.02] transition-transform shadow-xl shadow-primary/25 flex items-center gap-2">
                Get Started for Free
                <span className="material-symbols-outlined">arrow_forward</span>
            </button>
        </Link>
    );
}
