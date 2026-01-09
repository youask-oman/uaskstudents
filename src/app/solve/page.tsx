"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import ImageCropper from "@/components/ImageCropper";
import { useRouter } from "next/navigation";

export default function SessionWorkspacePage() {
    const [activeTab, setActiveTab] = useState<'steps' | 'verification' | 'concepts' | 'practice'>('steps');
    const [isDark, setIsDark] = useState(false);
    const [inputValue, setInputValue] = useState('');

    // OCR & Workflow State
    type WorkflowStage = 'idle' | 'selecting' | 'processing' | 'review' | 'error';
    // Solver State
    interface Step {
        title: string;
        content: string;
    }
    interface SolutionData {
        summary: string;
        steps: Step[];
        final_answer: string;
    }

    const [workflowStage, setWorkflowStage] = useState<WorkflowStage>('idle');
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [croppedImage, setCroppedImage] = useState<string | null>(null);
    const [progressStep, setProgressStep] = useState(0);
    const [processingTime, setProcessingTime] = useState(0);

    // New Solver States
    const [isSolving, setIsSolving] = useState(false);
    const [solution, setSolution] = useState<SolutionData | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

    const PROGRESS_STEPS = [
        { label: "Uploading crop...", percent: 20 },
        { label: "Analyzing with OpenAI Vision...", percent: 60 },
        { label: "Extracting LaTeX...", percent: 90 },
        { label: "Done", percent: 100 }
    ];

    const processFile = (file: File) => {
        console.log("Processing file selection...");
        if (!file) return;

        const objectUrl = URL.createObjectURL(file);
        setCapturedImage(objectUrl);
        setWorkflowStage('selecting');
    };

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) processFile(file);
    };

    const resetWorkflow = () => {
        setWorkflowStage('idle');
        setCapturedImage(null);
        setCroppedImage(null);
        setProgressStep(0);
        setProcessingTime(0);
    };

    const handleCropConfirm = async (blob: Blob) => {
        const croppedUrl = URL.createObjectURL(blob);
        setCroppedImage(croppedUrl);
        setWorkflowStage('processing');
        setProgressStep(0);
        setProcessingTime(0);

        // Timer for long running jobs warning
        const timer = setInterval(() => setProcessingTime(p => p + 1), 1000);

        try {
            const formData = new FormData();
            formData.append('file', blob, 'crop.jpg');

            // NEW: Direct call to OpenAI Vision Endpoint
            setProgressStep(1); // Analyzing...

            const res = await fetch('http://localhost:8000/api/v1/latex-from-image?user_id=1', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error("Analysis failed");

            const data = await res.json();

            // Success
            clearInterval(timer);
            setProgressStep(3); // Done

            setTimeout(() => {
                setInputValue(prev => {
                    const newText = data.latex || "";
                    return prev ? `${prev}\n\n${newText}` : newText;
                });
                setWorkflowStage('idle');
            }, 600);

        } catch (err) {
            console.error(err);
            clearInterval(timer);
            setWorkflowStage('error');
            alert("Analysis failed. Please check your connection or API key.");
        }
    };

    useEffect(() => {
        // Check initial preference logic
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
            setIsDark(true);
        } else {
            document.documentElement.classList.remove('dark');
            setIsDark(false);
        }
    }, []);

    // Math Rendering using KaTeX Auto-Render
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            // @ts-ignore
            if (window.renderMathInElement) {
                // @ts-ignore
                window.renderMathInElement(document.body, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '$', right: '$', display: false },
                        { left: '\\(', right: '\\)', display: false },
                        { left: '\\[', right: '\\]', display: true }
                    ],
                    throwOnError: false
                });
            }
        }, 1000);
        return () => clearTimeout(timeoutId);
    }, []);

    const toggleTheme = () => {
        if (isDark) {
            document.documentElement.classList.remove("dark");
            localStorage.theme = 'light';
            setIsDark(false);
        } else {
            document.documentElement.classList.add("dark");
            localStorage.theme = 'dark';
            setIsDark(true);
        }
    };

    const handleSolve = async () => {
        if (!inputValue.trim()) return;

        setIsSolving(true);
        setSolution(null);

        try {
            const res = await fetch('http://localhost:8000/api/v1/solve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text_query: inputValue,
                    mode: 'general'
                })
            });

            if (!res.ok) throw new Error("Solve request failed");

            const data = await res.json();
            // The API returns structured_data in solution field or wrapper
            // Adjust based on api.py response structure. 
            // Update: api.py returns SolveResponse(solution=dict, ...)
            setSolution(data.solution);

        } catch (err) {
            console.error(err);
            alert("Failed to generate solution");
        } finally {
            setIsSolving(false);
        }
    };

    return (
        <div className="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 min-h-screen flex flex-col font-display transition-colors duration-200">
            {/* Top Navigation Bar */}
            <header className="flex items-center justify-between border-b border-solid border-slate-200 dark:border-border-dark px-6 py-3 bg-white dark:bg-background-dark sticky top-0 z-50">
                <div className="flex items-center gap-8">
                    <Link href="/dashboard" className="flex items-center gap-3">
                        <div className="size-8 bg-primary rounded flex items-center justify-center text-white">
                            <span className="material-symbols-outlined">functions</span>
                        </div>
                        <h2 className="text-lg font-bold leading-tight tracking-tight">uask.ai</h2>
                    </Link>
                    <nav className="hidden md:flex items-center gap-6">
                        <Link className="text-sm font-medium hover:text-primary transition-colors" href="/dashboard">Dashboard</Link>
                        <Link className="text-sm font-medium text-primary border-b-2 border-primary pb-1" href="/solve">Workspace</Link>
                        <Link className="text-sm font-medium hover:text-primary transition-colors" href="#">Library</Link>
                    </nav>
                </div>
                <div className="flex items-center gap-4">
                    <button
                        onClick={toggleTheme}
                        className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-surface-dark rounded-full transition-colors flex items-center"
                        aria-label="Toggle Dark Mode"
                    >
                        <span className="material-symbols-outlined">{isDark ? 'light_mode' : 'dark_mode'}</span>
                    </button>
                    <div className="flex items-center gap-2">
                        <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-surface-dark transition-colors">
                            <span className="material-symbols-outlined text-xl">notifications</span>
                        </button>
                        <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-surface-dark transition-colors">
                            <span className="material-symbols-outlined text-xl">settings</span>
                        </button>
                    </div>
                    <div className="h-8 w-[1px] bg-slate-200 dark:border-border-dark mx-1"></div>
                    <div className="flex items-center gap-3">
                        <div className="bg-center bg-no-repeat aspect-square bg-cover rounded-full size-8 border border-primary/20" data-alt="User profile avatar minimalist illustration" style={{ backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuCJQsi4Do0nD_nSwlJFCO011UDnVu3_UDKt2G9Q5gveExIvrT5MN9m02DOXIufov9xZ58kpbjtpIrBhxNq1gY2FFwLQece5ba2IML-3TnlcXc2nfSnLtdtdHnrrtUnnIXik87tj-vEgtU70o_XwcU-BdznztoaXiTtH0V5VqrqTSLPsZRKoRF5EMk0ZkPmUGhK24U74jF4lFjCIAFqvbpJuBK2f44pMW6wo6Yfb0Rya5vehmfkV-87dqIBTdO3cggxDYjNDGNuo5abz")' }}></div>
                        <span className="text-sm font-medium hidden sm:inline">Alex Chen</span>
                    </div>
                </div>
            </header>

            <main className="flex flex-1 overflow-hidden h-[calc(100vh-65px)]">
                {/* Left Sidebar: Chat & OCR */}
                <aside className="w-80 flex-shrink-0 border-r border-slate-200 dark:border-border-dark flex flex-col bg-white dark:bg-background-dark">
                    <div className="p-4 border-b border-slate-200 dark:border-border-dark flex justify-between items-center">
                        <div className="flex items-center gap-2 text-primary font-semibold">
                            <span className="material-symbols-outlined text-lg">chat_bubble</span>
                            <span>Tutor Chat</span>
                        </div>
                        <button className="p-1 hover:bg-slate-100 dark:hover:bg-surface-dark rounded text-xs uppercase font-bold text-slate-500">History</button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {/* User Message */}
                        <div className="flex flex-col gap-1 items-end">
                            <div className="bg-primary text-white p-3 rounded-lg rounded-tr-none text-sm max-w-[90%]">
                                Help me solve this projectile motion problem. Initial velocity is 25m/s at 30°.
                            </div>
                            <span className="text-[10px] text-slate-500">10:42 AM</span>
                        </div>
                        {/* AI Message */}
                        <div className="flex flex-col gap-1 items-start">
                            <div className="flex items-center gap-2 mb-1">
                                <div className="size-5 bg-primary/20 rounded-full flex items-center justify-center">
                                    <span className="material-symbols-outlined text-[12px] text-primary">smart_toy</span>
                                </div>
                                <span className="text-xs font-bold">uask AI</span>
                            </div>
                            <div className="bg-slate-100 dark:bg-surface-dark p-3 rounded-lg rounded-tl-none text-sm max-w-[90%] leading-relaxed">
                                Understood. I'll break down the components and calculate the trajectory steps for you in the Solution Panel.
                            </div>
                        </div>
                        {/* AI Thought Process */}
                        <div className="border-l-2 border-slate-200 dark:border-border-dark ml-2 pl-4 py-1 space-y-2 opacity-60">
                            <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-sm">memory</span>
                                <span className="text-[11px] font-medium italic">Analyzing kinematic variables...</span>
                            </div>
                        </div>
                    </div>
                    {/* Chat Input / OCR */}
                    <div className="p-4 border-t border-slate-200 dark:border-border-dark bg-slate-50 dark:bg-background-dark">
                        <div className="relative">
                            <textarea
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                className="w-full bg-white dark:bg-surface-dark border border-slate-200 dark:border-border-dark rounded-xl px-4 py-3 text-sm focus:ring-1 focus:ring-primary focus:border-primary resize-none pr-12"
                                placeholder={
                                    workflowStage === 'processing'
                                        ? "Analyzing..."
                                        : "Ask a question..."
                                }
                                rows={3}
                                disabled={workflowStage === 'processing'}
                            ></textarea>
                            <div className="absolute right-2 bottom-3 flex gap-1">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    onChange={handleFileUpload}
                                    accept="image/*"
                                />
                                <button
                                    onClick={() => fileInputRef.current?.click()}
                                    className={`p-2 transition-colors ${workflowStage === 'processing' ? 'text-primary animate-pulse' : 'text-slate-400 hover:text-primary'}`}
                                    disabled={workflowStage === 'processing' || workflowStage === 'selecting'}
                                >
                                    <span className="material-symbols-outlined">photo_camera</span>
                                </button>
                                <button
                                    onClick={handleSolve}
                                    disabled={isSolving || !inputValue.trim()}
                                    className={`p-2 bg-primary text-white rounded-lg transition-colors ${isSolving || !inputValue.trim() ? 'opacity-50 cursor-not-allowed' : 'hover:bg-primary/90'}`}
                                >
                                    {isSolving ? (
                                        <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
                                    ) : (
                                        <span className="material-symbols-outlined text-sm">send</span>
                                    )}
                                </button>
                            </div>
                        </div>
                        <div className="mt-2 flex items-center justify-between px-1">
                            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Tutor Mode: Calculus &amp; Mechanics</span>
                            <button className="text-[10px] text-primary font-bold hover:underline">Change</button>
                        </div>
                    </div>
                </aside>

                {/* Main Solution Panel */}
                <div className="flex-1 flex flex-col bg-slate-50 dark:bg-[#0d1117] overflow-hidden">
                    {/* Progress / Streaming Indicator */}
                    <div className="px-6 py-3 border-b border-slate-200 dark:border-border-dark bg-white dark:bg-background-dark">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                                </span>
                                <h3 className="text-sm font-semibold">Generating Solution</h3>
                            </div>
                            <span className="text-xs font-medium text-slate-500">Step 3 of 4 · 75% Complete</span>
                        </div>
                        <div className="w-full h-1 bg-slate-100 dark:bg-surface-dark rounded-full overflow-hidden">
                            <div className="bg-primary h-full rounded-full transition-all duration-500" style={{ width: '75%' }}></div>
                        </div>
                    </div>

                    {/* Tab Navigation */}
                    <div className="bg-white dark:bg-background-dark px-6 border-b border-slate-200 dark:border-border-dark">
                        <div className="flex gap-8">
                            <button
                                onClick={() => setActiveTab('steps')}
                                className={`flex items-center gap-2 py-4 border-b-2 font-bold text-sm transition-colors ${activeTab === 'steps' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-lg">format_list_numbered</span>
                                Steps
                            </button>
                            <button
                                onClick={() => setActiveTab('verification')}
                                className={`flex items-center gap-2 py-4 border-b-2 font-medium text-sm transition-colors ${activeTab === 'verification' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-lg">verified</span>
                                Verification
                            </button>
                            <button
                                onClick={() => setActiveTab('concepts')}
                                className={`flex items-center gap-2 py-4 border-b-2 font-medium text-sm transition-colors ${activeTab === 'concepts' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-lg">auto_stories</span>
                                Concepts
                            </button>
                            <button
                                onClick={() => setActiveTab('practice')}
                                className={`flex items-center gap-2 py-4 border-b-2 font-medium text-sm transition-colors ${activeTab === 'practice' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-white'}`}
                            >
                                <span className="material-symbols-outlined text-lg">quiz</span>
                                Practice
                            </button>
                        </div>
                    </div>

                    {/* Solution Content Area */}
                    <div className="flex-1 overflow-y-auto p-8 max-w-4xl mx-auto w-full space-y-8">

                        {isSolving && (
                            <div className="flex flex-col items-center justify-center py-20 opacity-50">
                                <div className="size-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
                                <p className="text-lg font-bold text-slate-500">Generating Step-by-Step Solution...</p>
                                <p className="text-sm text-slate-400">Consulting external knowledge bases</p>
                            </div>
                        )}

                        {!isSolving && !solution && (
                            <div className="flex flex-col items-center justify-center py-20 opacity-40">
                                <span className="material-symbols-outlined text-6xl mb-4">school</span>
                                <p className="text-lg font-bold">Ready to Learn</p>
                                <p className="text-sm">Enter a problem or upload an image to start.</p>
                            </div>
                        )}

                        {!isSolving && solution && (
                            <>
                                <div className="flex items-center justify-between">
                                    <h1 className="text-2xl font-bold tracking-tight">{solution.summary}</h1>
                                    <div className="flex gap-2">
                                        <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold border border-slate-200 dark:border-border-dark rounded-lg hover:bg-white dark:hover:bg-surface-dark transition-colors">
                                            <span className="material-symbols-outlined text-sm">download</span>
                                            Export PDF
                                        </button>
                                        <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">
                                            <span className="material-symbols-outlined text-sm">share</span>
                                            Share
                                        </button>
                                    </div>
                                </div>

                                {solution.steps.map((step, idx) => (
                                    <div key={idx} className="bg-white dark:bg-surface-dark rounded-xl border border-slate-200 dark:border-border-dark shadow-sm overflow-hidden">
                                        <div className="bg-slate-50 dark:bg-white/5 px-6 py-3 border-b border-slate-200 dark:border-border-dark flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <span className="flex items-center justify-center size-6 bg-primary text-white text-xs font-bold rounded">{idx + 1}</span>
                                                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-500">{step.title}</h4>
                                            </div>
                                            <button className="text-primary"><span className="material-symbols-outlined text-lg">info</span></button>
                                        </div>
                                        <div className="p-6">
                                            <div className="bg-slate-50 dark:bg-[#0d1117] p-4 rounded-lg flex flex-col items-start gap-3 border border-slate-100 dark:border-border-dark">
                                                {/* Render math content */}
                                                <div className="text-base leading-relaxed">
                                                    {step.content.split('\n').map((line, i) => (
                                                        <p key={i} className="mb-2 latex-block">{line}</p>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {/* Final Answer */}
                                <div className="bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 rounded-xl p-6">
                                    <h4 className="text-sm font-bold uppercase tracking-wider text-green-700 dark:text-green-400 mb-2">Final Answer</h4>
                                    <div className="text-xl font-bold text-green-800 dark:text-green-200">
                                        {solution.final_answer}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Context Action Bar */}
                    <div className="p-4 bg-white dark:bg-background-dark border-t border-slate-200 dark:border-border-dark flex justify-center gap-4">
                        <button className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-surface-dark rounded-lg text-sm font-bold hover:bg-slate-200 dark:hover:bg-border-dark transition-colors">
                            <span className="material-symbols-outlined text-lg">psychology_alt</span>
                            Explain the logic
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-surface-dark rounded-lg text-sm font-bold hover:bg-slate-200 dark:hover:bg-border-dark transition-colors">
                            <span className="material-symbols-outlined text-lg">add_circle</span>
                            Apply air resistance
                        </button>
                        <button className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-surface-dark rounded-lg text-sm font-bold hover:bg-slate-200 dark:hover:bg-border-dark transition-colors">
                            <span className="material-symbols-outlined text-lg">science</span>
                            Simulate Lab
                        </button>
                    </div>
                </div>

                {/* Right Toolbelt (Collapsible) */}
                <aside className="w-14 flex-shrink-0 border-l border-slate-200 dark:border-border-dark flex flex-col items-center py-6 gap-6 bg-white dark:bg-background-dark">
                    <button className="group relative p-2 rounded-lg hover:bg-primary/10 transition-colors">
                        <span className="material-symbols-outlined text-slate-500 group-hover:text-primary">draw</span>
                        <span className="absolute left-[-80px] top-1 bg-slate-800 text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">Canvas</span>
                    </button>
                    <button className="group relative p-2 rounded-lg hover:bg-primary/10 transition-colors">
                        <span className="material-symbols-outlined text-slate-500 group-hover:text-primary">calculate</span>
                        <span className="absolute left-[-90px] top-1 bg-slate-800 text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">Calculator</span>
                    </button>
                    <button className="group relative p-2 rounded-lg hover:bg-primary/10 transition-colors">
                        <span className="material-symbols-outlined text-slate-500 group-hover:text-primary">book</span>
                        <span className="absolute left-[-95px] top-1 bg-slate-800 text-white text-[10px] py-1 px-2 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">Reference</span>
                    </button>
                    <div className="flex-1"></div>
                    <button className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white">
                        <span className="material-symbols-outlined">help_outline</span>
                    </button>
                </aside>
            </main>

            {/* OVERLAYS */}

            {/* STAGE: SELECTION */}
            {workflowStage === 'selecting' && capturedImage && (
                <div className="fixed inset-0 z-[100] bg-slate-900 flex flex-col">
                    <ImageCropper
                        imageSrc={capturedImage}
                        onCancel={resetWorkflow}
                        onConfirm={handleCropConfirm}
                    />
                </div>
            )}

            {/* STAGE: PROCESSING */}
            {workflowStage === 'processing' && (
                <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl p-8 max-w-md w-full shadow-2xl border border-slate-200 dark:border-slate-700">
                        <div className="text-center space-y-6">
                            {/* Animated Icon */}
                            <div className="relative size-20 mx-auto">
                                <div className="absolute inset-0 border-4 border-slate-100 dark:border-slate-800 rounded-full"></div>
                                <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className="material-symbols-outlined text-3xl text-primary font-bold">document_scanner</span>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <h3 className="text-xl font-bold dark:text-white">
                                    {PROGRESS_STEPS[progressStep]?.label || "Processing..."}
                                </h3>
                                <p className="text-sm text-slate-500">
                                    Please wait while we analyze your image.
                                </p>
                            </div>

                            {/* Progress Bar */}
                            <div className="space-y-2">
                                <div className="flex justify-between text-xs font-bold text-slate-400 uppercase tracking-widest">
                                    <span>Progress</span>
                                    <span>{PROGRESS_STEPS[progressStep]?.percent || 0}%</span>
                                </div>
                                <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-primary transition-all duration-500 ease-out"
                                        style={{ width: `${PROGRESS_STEPS[progressStep]?.percent || 0}%` }}
                                    ></div>
                                </div>
                            </div>

                            {/* Long Loading Warning */}
                            {(processingTime > 8) && (
                                <div className="flex gap-3 items-start p-3 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-lg text-xs text-left">
                                    <span className="material-symbols-outlined text-sm shrink-0">info</span>
                                    <p>This is taking a bit longer than usual (likely initializing the math models). Thanks for your patience!</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
