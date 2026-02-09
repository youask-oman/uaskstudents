'use client';

import React from 'react';

export default function InvoicesPage() {
    return (
        <div className="p-8 max-w-6xl">
            <h1 className="text-2xl font-bold mb-6">🧾 Invoice Center</h1>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                <div className="text-4xl mb-4">🚧</div>
                <h2 className="text-xl font-bold text-yellow-800 mb-2">Coming Soon</h2>
                <p className="text-yellow-700">
                    Invoice management functionality is under development.
                </p>
                <p className="text-sm text-yellow-600 mt-2">
                    This will include viewing immutable invoices, line items, and PDF export.
                </p>
            </div>
        </div>
    );
}
