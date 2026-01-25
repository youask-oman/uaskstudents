 "use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useLayoutEffect,
    useMemo,
    useState,
} from "react";

type ThemeMode = "dark" | "light";

const STORAGE_KEY = "theme";

const getPreferredTheme = (): ThemeMode => {
    if (typeof window === "undefined") {
        return "light";
    }
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
        return stored;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const applyTheme = (theme: ThemeMode) => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (theme === "dark") {
        root.classList.add("dark");
    } else {
        root.classList.remove("dark");
    }
    root.dataset.theme = theme;
};

interface ThemeContextValue {
    theme: ThemeMode;
    isDark: boolean;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const useIsomorphicLayoutEffect =
    typeof window !== "undefined" ? useLayoutEffect : useEffect;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setTheme] = useState<ThemeMode>(() => getPreferredTheme());

    const toggleTheme = useCallback(() => {
        setTheme((prev) => {
            const next = prev === "dark" ? "light" : "dark";
            if (typeof window !== "undefined") {
                try {
                    localStorage.setItem(STORAGE_KEY, next);
                } catch (error) {
                    console.warn("Unable to persist theme", error);
                }
            }
            return next;
        });
    }, []);

    useIsomorphicLayoutEffect(() => {
        applyTheme(theme);
    }, [theme]);

    useEffect(() => {
        if (typeof window === "undefined") return;

        const stored = localStorage.getItem(STORAGE_KEY);
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const targetTheme: ThemeMode =
            stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light";

        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTheme((prev) => (prev === targetTheme ? prev : targetTheme));

        const handleStorage = (event: StorageEvent) => {
            if (event.key !== STORAGE_KEY) return;
            if (event.newValue === "dark" || event.newValue === "light") {
                setTheme(event.newValue);
            }
        };

        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleMediaChange = (event: MediaQueryListEvent) => {
            const storedValue = localStorage.getItem(STORAGE_KEY);
            if (storedValue === "dark" || storedValue === "light") return;
            setTheme(event.matches ? "dark" : "light");
        };

        const addMediaListener = () => {
            if (typeof mediaQuery.addEventListener === "function") {
                mediaQuery.addEventListener("change", handleMediaChange);
                return () => mediaQuery.removeEventListener("change", handleMediaChange);
            }
            if (typeof mediaQuery.addListener === "function") {
                mediaQuery.addListener(handleMediaChange);
                return () => mediaQuery.removeListener(handleMediaChange);
            }
            return () => {};
        };

        window.addEventListener("storage", handleStorage);
        const cleanupMedia = addMediaListener();

        return () => {
            window.removeEventListener("storage", handleStorage);
            cleanupMedia();
        };
    }, []);

    const value = useMemo(
        () => ({
            theme,
            isDark: theme === "dark",
            toggleTheme,
        }),
        [theme, toggleTheme]
    );

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error("useTheme must be used within ThemeProvider");
    }
    return context;
}
