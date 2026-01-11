export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="font-admin bg-admin-bg-dark text-slate-200 min-h-screen flex overflow-hidden">
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 bg-[#0c1222] border-r border-slate-800 flex flex-col justify-between p-4">
                <div className="flex flex-col gap-8">
                    <div className="flex items-center gap-3 px-2">
                        <img src="/logo-dark.png" alt="uask.ai" className="h-8 w-auto" />
                        <div className="flex flex-col">
                            <h1 className="text-white text-base font-bold leading-none">uask.ai</h1>
                            <p className="text-slate-500 text-[10px] uppercase tracking-widest font-semibold mt-1">Admin Panel</p>
                        </div>
                    </div>
                    <nav className="flex flex-col gap-1">
                        <a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors" href="#">
                            <span className="material-symbols-outlined">analytics</span>
                            <p className="text-sm font-medium">Usage</p>
                        </a>
                        <a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors" href="#">
                            <span className="material-symbols-outlined">description</span>
                            <p className="text-sm font-medium">Content</p>
                        </a>
                        <a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors" href="#">
                            <span className="material-symbols-outlined">memory</span>
                            <p className="text-sm font-medium">Models</p>
                        </a>
                        <a className="flex items-center gap-3 px-3 py-2.5 rounded-lg active-nav text-white" href="#">
                            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>speed</span>
                            <p className="text-sm font-medium">Performance</p>
                        </a>
                    </nav>
                </div>
                <div className="flex flex-col gap-4">
                    <button className="w-full py-2.5 bg-admin-primary hover:bg-admin-primary/90 text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-admin-primary/20 flex items-center justify-center gap-2">
                        <span className="material-symbols-outlined text-sm">add</span>
                        New Report
                    </button>
                    <div className="flex items-center gap-3 px-2 py-2 border-t border-slate-800 pt-4">
                        <div className="size-8 rounded-full bg-slate-700 bg-cover bg-center" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuBwECVGTs6iH9XO-B4jESf2X0FNVdKTGxwWZcFQOSAdWfZSA_2zsDdWGWDczmedXdsF4R_nsqP0M38kytuwB9Bqhr1JA6QRd_-rkVvrs2-wAnUiRPq26a19CckAKrbrpSYe2GpBL1n0kz7QMzmoOABhjrZrbqx2-P-vGovPVlZjZzBpZwVtKGSA2wdXZyWy0T3ISVJHq-Fmy4ySsRXMQXDivdERw_8fVe_9x8QL1hDSSXgvBn2iFAv1Hy3O0r_fA8Uiw_AmFMmCxnwq")' }}></div>
                        <div className="flex flex-col">
                            <p className="text-white text-xs font-bold">Alex Rivera</p>
                            <p className="text-slate-500 text-[10px]">Super Admin</p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content Shell */}
            <main className="flex-1 flex flex-col overflow-y-auto w-full">
                {children}
            </main>
        </div>
    );
}
