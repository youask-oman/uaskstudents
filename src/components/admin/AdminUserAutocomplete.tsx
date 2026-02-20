"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

type AdminUserLookupItem = {
    id: number;
    email: string;
    full_name?: string | null;
    role?: string | null;
};

type AdminUsersResponse = {
    users?: AdminUserLookupItem[];
};

type Props = {
    value: string;
    onValueChange: (value: string) => void;
    onSelect?: (user: AdminUserLookupItem) => void;
    placeholder?: string;
    className?: string;
    inputClassName?: string;
    minChars?: number;
};

export default function AdminUserAutocomplete({
    value,
    onValueChange,
    onSelect,
    placeholder = "Lookup user by email",
    className,
    inputClassName,
    minChars = 2,
}: Props) {
    const [items, setItems] = useState<AdminUserLookupItem[]>([]);
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const query = value.trim();

    useEffect(() => {
        if (query.length < minChars) {
            setItems([]);
            return;
        }

        let cancelled = false;
        const timer = setTimeout(async () => {
            setLoading(true);
            try {
                const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
                const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
                const res = await fetchApi(`/api/v1/admin/users?q=${encodeURIComponent(query)}&limit=8`, { headers });
                if (!res.ok) {
                    if (!cancelled) setItems([]);
                    return;
                }
                const data = (await res.json()) as AdminUsersResponse;
                const nextItems = Array.isArray(data.users) ? data.users : [];
                if (!cancelled) {
                    setItems(nextItems);
                    setOpen(true);
                }
            } catch {
                if (!cancelled) setItems([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }, 250);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [minChars, query]);

    useEffect(() => {
        return () => {
            if (blurTimer.current) clearTimeout(blurTimer.current);
        };
    }, []);

    const showDropdown = useMemo(() => open && (loading || items.length > 0), [items.length, loading, open]);

    return (
        <div className={`relative ${className || ""}`}>
            <input
                type="text"
                value={value}
                onChange={(e) => onValueChange(e.target.value)}
                placeholder={placeholder}
                onFocus={() => {
                    if (query.length >= minChars) setOpen(true);
                }}
                onBlur={() => {
                    blurTimer.current = setTimeout(() => setOpen(false), 120);
                }}
                className={inputClassName || "w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"}
            />

            {showDropdown && (
                <div className="absolute z-40 mt-1 w-full max-h-64 overflow-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg">
                    {loading && <div className="px-3 py-2 text-xs text-slate-500">Searching users...</div>}
                    {!loading && items.map((user) => (
                        <button
                            key={user.id}
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                                onValueChange(user.email);
                                onSelect?.(user);
                                setOpen(false);
                            }}
                            className="w-full px-3 py-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                            <div className="text-sm font-semibold text-slate-900 dark:text-white">{user.email}</div>
                            <div className="text-xs text-slate-500">#{user.id}{user.full_name ? ` - ${user.full_name}` : ""}{user.role ? ` - ${user.role}` : ""}</div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
