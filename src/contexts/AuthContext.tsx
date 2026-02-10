'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

interface AuthContextType {
    token: string | null;
    isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
    token: null,
    isAuthenticated: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
    const [token] = useState<string | null>(() => {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem('token');
    });

    return (
        <AuthContext.Provider value={{ token, isAuthenticated: !!token }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}

export default AuthContext;
