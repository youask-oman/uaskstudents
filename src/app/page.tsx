import Link from "next/link";
import TopNavBar from "@/components/TopNavBar";
import Footer from "@/components/Footer";
import HeroCTA from "@/components/HeroCTA";
import PricingSection from "@/components/PricingSection";

export default function Home() {
  return (
    <>
      <TopNavBar />
      <main>
        {/* HeroSection */}
        <section className="max-w-[1200px] mx-auto px-4 py-16 md:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="flex flex-col gap-8">
              <div className="flex flex-col gap-4">
                <span className="px-3 py-1 bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider rounded-full w-fit">AI-Powered Learning</span>
                <h1 className="text-5xl md:text-6xl font-black leading-tight tracking-tight font-display text-[#111318] dark:text-white">
                  Master Math & Physics <br /><span className="text-primary">with AI</span>
                </h1>
                <p className="text-lg text-[#616f89] dark:text-gray-400 max-w-[500px]">
                  Snap a photo, get step-by-step guidance, and master complex concepts in seconds. Your personal tutor, available 24/7.
                </p>
              </div>
              <div className="flex flex-wrap gap-4">
                <HeroCTA />
                <button className="h-14 px-8 bg-white dark:bg-slate-800 border border-[#dbdfe6] dark:border-slate-700 text-[#111318] dark:text-white rounded-xl font-bold text-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors">
                  Watch Demo
                </button>
              </div>
              <div className="flex items-center gap-4 text-sm text-[#616f89]">
                <div className="flex -space-x-2">
                  <div className="w-8 h-8 rounded-full bg-blue-200 border-2 border-white dark:border-background-dark flex items-center justify-center font-bold text-[10px] text-blue-700">JD</div>
                  <div className="w-8 h-8 rounded-full bg-green-200 border-2 border-white dark:border-background-dark flex items-center justify-center font-bold text-[10px] text-green-700">AS</div>
                  <div className="w-8 h-8 rounded-full bg-purple-200 border-2 border-white dark:border-background-dark flex items-center justify-center font-bold text-[10px] text-purple-700">MK</div>
                </div>
                <span>Joined by 10,000+ students this month</span>
              </div>
            </div>
            {/* Graphic Hero Split View */}
            <div className="relative group">
              <div className="absolute -inset-4 bg-gradient-to-tr from-primary/20 to-purple-500/10 blur-3xl rounded-full opacity-50"></div>
              <div className="relative bg-white dark:bg-slate-900 border border-[#dbdfe6] dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden aspect-[4/3] flex">
                {/* Left: Raw Image */}
                <div className="w-1/2 relative overflow-hidden border-r border-[#dbdfe6] dark:border-slate-700">
                  <div className="absolute inset-0 bg-cover bg-center opacity-80" data-alt="Close up of handwritten complex physics equation on paper" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuAFP7ZdnzXyFFhBZX8qVE-U3sj5S3twiJKm7wVlTgSj9lQ6MR3E3pKcwR0KobTuvn3i9hA-y7WITjEPsLJz6ZfxCn5XXP9HiB5sbbTW9svAHmvU7yDevf4X3UcjyNkJKRGN5RftLdtW3E8_msS3AwGSiqRSxs_M7ciq2BcfpyYDKYSZ7ycD_QPRSJywyA2IlemeWJMNxee1ldeKpPZQzJ8EQ9CwOjZzI8gzRHgcXVu-8NLdQn-KryBXlgB_lzZt854KQd_vHGUyeikA")' }}></div>
                  <div className="absolute inset-0 bg-black/20"></div>
                  <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur px-2 py-1 rounded text-[10px] font-bold text-[#111318]">RAW SCAN</div>
                </div>
                {/* Right: LaTeX Digital */}
                <div className="w-1/2 bg-white dark:bg-slate-900 flex flex-col items-center justify-center p-6">
                  <div className="space-y-4 w-full">
                    <div className="h-2 w-24 bg-primary/20 rounded"></div>
                    <div className="p-4 bg-primary/5 rounded-lg border border-primary/10 flex flex-col items-center">
                      <div className="text-primary text-xl font-serif italic">∫ e<sup>x²</sup> dx</div>
                      <div className="mt-4 h-1 w-full bg-primary/10 rounded overflow-hidden">
                        <div className="h-full bg-primary w-2/3"></div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="h-2 w-full bg-gray-100 dark:bg-slate-800 rounded"></div>
                      <div className="h-2 w-5/6 bg-gray-100 dark:bg-slate-800 rounded"></div>
                      <div className="h-2 w-4/6 bg-gray-100 dark:bg-slate-800 rounded"></div>
                    </div>
                  </div>
                  <div className="absolute bottom-4 right-4 bg-primary/90 text-white px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide">LaTeX Render</div>
                </div>
                {/* Scanning Line */}
                <div className="absolute top-0 bottom-0 left-1/2 w-1 bg-primary shadow-[0_0_15px_rgba(19,91,236,0.8)] z-10"></div>
              </div>
            </div>
          </div>
        </section>

        {/* SectionHeader & TextGrid (How it Works) */}
        <section className="bg-white dark:bg-slate-900/50 py-20 border-y border-[#f0f2f4] dark:border-slate-800 transition-colors duration-200" id="how-it-works">
          <div className="max-w-[1200px] mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold font-display mb-4 text-[#111318] dark:text-white">How it Works</h2>
              <p className="text-[#616f89] dark:text-gray-400">Mastering tough problems is as easy as 1-2-3</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-background-light dark:bg-slate-800 border border-[#dbdfe6] dark:border-slate-700 hover:border-primary/50 transition-colors group">
                <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl">photo_camera</span>
                </div>
                <h3 className="text-xl font-bold mb-3 font-display text-[#111318] dark:text-white">1. Snap</h3>
                <p className="text-sm text-[#616f89] dark:text-gray-400 leading-relaxed">
                  Take a photo of your textbook, homework, or whiteboard notes. Our AI handles handwriting with 99% accuracy.
                </p>
              </div>
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-background-light dark:bg-slate-800 border border-[#dbdfe6] dark:border-slate-700 hover:border-primary/50 transition-colors group">
                <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl">analytics</span>
                </div>
                <h3 className="text-xl font-bold mb-3 font-display text-[#111318] dark:text-white">2. Review</h3>
                <p className="text-sm text-[#616f89] dark:text-gray-400 leading-relaxed">
                  Watch as formulas are digitized into clean LaTeX. Confirm the scan and see instant concept tags related to your problem.
                </p>
              </div>
              <div className="flex flex-col items-center text-center p-8 rounded-2xl bg-background-light dark:bg-slate-800 border border-[#dbdfe6] dark:border-slate-700 hover:border-primary/50 transition-colors group">
                <div className="w-16 h-16 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl">psychology</span>
                </div>
                <h3 className="text-xl font-bold mb-3 font-display text-[#111318] dark:text-white">3. Solve</h3>
                <p className="text-sm text-[#616f89] dark:text-gray-400 leading-relaxed">
                  Don't just get the answer. Our Socratic AI guides you through the logic, asking the right questions to ensure you learn.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FeatureSection */}
        <section className="py-24 max-w-[1200px] mx-auto px-4" id="features">
          <div className="flex flex-col gap-16">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
              <div className="max-w-[720px]">
                <h2 className="text-4xl md:text-5xl font-black font-display tracking-tight mb-4 text-[#111318] dark:text-white">
                  Engineered for Academic Excellence
                </h2>
                <p className="text-lg text-[#616f89] dark:text-gray-400">
                  Beyond a calculator. We built tools to help you understand the 'why' behind every solution.
                </p>
              </div>
              <div className="flex items-center gap-2 text-primary font-bold cursor-pointer hover:underline">
                Explore all features <span className="material-symbols-outlined">trending_flat</span>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="flex flex-col gap-4 group">
                <div className="w-full bg-center bg-no-repeat aspect-video bg-cover rounded-xl shadow-lg group-hover:shadow-primary/10 transition-shadow overflow-hidden" data-alt="UI showing complex calculus formula being highlighted and digitized" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuBTkENaFWGY07yuXC8OVUqVXIX_yPTwhTAee96LA4caUyidtwEZLMaXjlZzv7zP7ZOqp3ibMjlDnYnBK_wkmmYHjKOAohaSFMPPUjPUuZ5-rwoFT9dbK-ut9ZVm856Doxy8CJfTyosNgEVGI2EKgA_-Tor72M_8nP3UCse2DbspAo3s8E2WrbiDnxk7KSEqHXLdIIz-li4bfIHWmkYUZ1AJwTNVaYNWM2meGi2kDkeWQsd2pJz1P1PZ-vT1IcZHODdvxOIKNrkwpvLb")' }}>
                  <div className="w-full h-full bg-primary/10 backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="bg-white text-primary px-4 py-2 rounded-full font-bold text-sm">View Demo</span>
                  </div>
                </div>
                <div>
                  <p className="text-xl font-bold font-display mb-1 text-[#111318] dark:text-white">OCR for Math</p>
                  <p className="text-[#616f89] dark:text-gray-400 text-sm leading-relaxed">Precision recognition for the most complex Greek symbols, subscripts, and nested fractions.</p>
                </div>
              </div>
              <div className="flex flex-col gap-4 group">
                <div className="w-full bg-center bg-no-repeat aspect-video bg-cover rounded-xl shadow-lg group-hover:shadow-primary/10 transition-shadow overflow-hidden" data-alt="Interface of AI chat showing a tutoring dialogue with diagrams" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuAOZ-p19_vKizH2ck-SqAyi-WkPFTghvppMXf9T9We7WKhXCO2z7TBlHcBbN1N_dPiW11cf_BQsLIKQOVpq7RDUayDXH7FyTOMwsa_xDutjBD4--m6Pz9Z7xbjDoBM-2H38zD57RUsIc8t0BcCjyjbOnT1kvUGXPil7r870BGxm4MLpqSCLWBXeACmIFNls4nEjDJdnb6E2hfBKn1q92l7k5noCO67SKDKIkEDVkYt0LxpRNabpEnkizLyIlADaVmECXlo41BtPOF9D")' }}>
                  <div className="w-full h-full bg-primary/10 backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="bg-white text-primary px-4 py-2 rounded-full font-bold text-sm">View Demo</span>
                  </div>
                </div>
                <div>
                  <p className="text-xl font-bold font-display mb-1 text-[#111318] dark:text-white">Socratic Tutoring</p>
                  <p className="text-[#616f89] dark:text-gray-400 text-sm leading-relaxed">Learn by doing with an AI that prompts you for the next logical step instead of just giving answers.</p>
                </div>
              </div>
              <div className="flex flex-col gap-4 group">
                <div className="w-full bg-center bg-no-repeat aspect-video bg-cover rounded-xl shadow-lg group-hover:shadow-primary/10 transition-shadow overflow-hidden" data-alt="A library interface with various physics laws and math theorems cards" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuDNuPpHOfvlMast3R3Ti_CuEBLoqnbOwqFAMQwE8Ex9tBwcDE4SIrB_yJiU0p52ymHyvjbM-wNBUNXFTjzvfghnb1T_hgziUy3DwXwDG_HPewLpoPAhkoSLksO0A43ltvBXrmobD06T18TEtJV62AjSrOKaMtacjU7QWLkyL8xdt3vRVnOp55ubXtkv8r7eacotps6ISk1mm-9c0nyBdCWHtbhIf-ELMvt7oZsVEjZoM_uMP0pYU1VsZdetiMDwPaLcgyMvRi2IXl2R")' }}>
                  <div className="w-full h-full bg-primary/10 backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="bg-white text-primary px-4 py-2 rounded-full font-bold text-sm">View Demo</span>
                  </div>
                </div>
                <div>
                  <p className="text-xl font-bold font-display mb-1 text-[#111318] dark:text-white">Concept Library</p>
                  <p className="text-[#616f89] dark:text-gray-400 text-sm leading-relaxed">Instant access to a wiki of related physics laws, constants, and mathematical theorems.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <PricingSection />

        {/* Final CTA */}
        <section className="py-24 max-w-[1200px] mx-auto px-4 text-center">
          <div className="bg-primary rounded-3xl p-12 md:p-20 text-white relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '40px 40px' }}></div>
            <div className="relative z-10">
              <h2 className="text-4xl md:text-5xl font-black font-display mb-6">Ready to Ace Your Exams?</h2>
              <p className="text-lg opacity-90 mb-10 max-w-[600px] mx-auto">Join thousands of students using uask.ai to turn confusion into clarity every single day.</p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link href="/signup">
                  <button className="px-10 py-4 bg-white text-primary rounded-xl font-bold text-lg hover:scale-105 transition-transform shadow-xl">Create Free Account</button>
                </Link>
                <button className="px-10 py-4 bg-primary border border-white/30 rounded-xl font-bold text-lg hover:bg-white/10 transition-colors">Download App</button>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
