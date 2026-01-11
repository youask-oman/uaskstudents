export default function Footer() {
    return (
        <footer className="border-t border-[#f0f2f4] dark:border-slate-800 py-12 bg-white dark:bg-background-dark transition-colors duration-200">
            <div className="max-w-[1200px] mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-8">
                <div className="flex items-center gap-3">
                    <img src="/logo.png" alt="uask.ai" className="h-6 w-auto block dark:hidden" />
                    <img src="/logo-dark.png" alt="uask.ai" className="h-6 w-auto hidden dark:block" />
                    <h2 className="text-[#111318] dark:text-white text-lg font-bold font-display">uask.ai</h2>
                </div>
                <div className="flex gap-8 text-sm text-[#616f89] dark:text-gray-400">
                    <a className="hover:text-primary transition-colors" href="#">Terms</a>
                    <a className="hover:text-primary transition-colors" href="#">Privacy</a>
                    <a className="hover:text-primary transition-colors" href="#">Contact</a>
                    <a className="hover:text-primary transition-colors" href="#">Twitter</a>
                </div>
                <p className="text-xs text-[#616f89] dark:text-gray-500">© 2024 uask.ai. All rights reserved.</p>
            </div>
        </footer>
    );
}
