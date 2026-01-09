"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import katex from 'katex';
import MathInput, { MathInputRef } from "@/components/MathInput";
import { MODES, ModeId, Suggestion } from "@/lib/modes";
import ImageCropper from "@/components/ImageCropper";

interface ChatSession {
    id: number;
    title: string;
    created_at: string;
}

export default function DashboardPage() {
    const [activeTab, setActiveTab] = useState<'text' | 'snap' | 'voice'>('text');
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [query, setQuery] = useState("sqrt(x+5) = x - 1");
    const [isSolving, setIsSolving] = useState(false);

    // Editor State
    const [activeMode, setActiveMode] = useState<ModeId | null>(null);
    const mathInputRef = useRef<MathInputRef>(null);

    const router = useRouter();

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            router.push("/login");
            return;
        }

        const fetchHistory = async () => {
            try {
                const response = await fetch(`http://localhost:8000/api/v1/history?user_id=${userId}`);
                if (response.ok) {
                    const data = await response.json();
                    setHistory(data);
                }
            } catch (error) {
                console.error("Failed to fetch history:", error);
            }
        };

        fetchHistory();
    }, [router]);

    const handleSuggestionClick = (suggestion: Suggestion) => {
        if (!mathInputRef.current) return;

        if (suggestion.insertMode === 'replace') {
            setQuery(suggestion.latex.replace(/#\?/g, '')); // Basic cleanup if direct set, or let MathInput handle it
            // Actually, MathLive behaves better if we use setValue for full replace
            mathInputRef.current.setValue(suggestion.latex);
        } else {
            mathInputRef.current.insert(suggestion.latex);
        }
        // Optionally close dropdown or keep open. Let's keep open for rapid exploration, or close?
        // User spec: "Clicking a suggestion: Inserts... OR Replaces..."
        // Let's keep it open if it's "append", close if "replace"? 
        // For now, let's just focus the input
        mathInputRef.current.focus();
    };

    const handleClear = () => {
        setQuery("");
        if (mathInputRef.current) {
            mathInputRef.current.setValue("");
            mathInputRef.current.focus();
        }
    };

    // OCR & Workflow State
    const [workflowStage, setWorkflowStage] = useState<'input' | 'selecting' | 'processing' | 'review'>('input');
    const [capturedImage, setCapturedImage] = useState<string | null>(null);
    const [croppedImage, setCroppedImage] = useState<string | null>(null);
    const [ocrConfidence, setOcrConfidence] = useState<number>(0);
    const [progressStep, setProgressStep] = useState(0);
    const [processingTime, setProcessingTime] = useState(0);

    const PROGRESS_STEPS = [
        { label: "Uploading crop...", percent: 20 },
        { label: "Analyzing with YouAsk.ai Vision...", percent: 60 },
        { label: "Extracting LaTeX...", percent: 90 },
        { label: "Done!", percent: 100 }
    ];

    const processFile = (file: File) => {
        if (!file) return;
        const objectUrl = URL.createObjectURL(file);
        setCapturedImage(objectUrl);
        setWorkflowStage('selecting');
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

            const userId = localStorage.getItem("user_id") || "1";

            // Step 1: Uploading
            setProgressStep(0);

            // Step 2: Analyzing (simulated delay for UX if network is too fast, or just let it fly)
            setTimeout(() => setProgressStep(1), 500);

            const res = await fetch(`http://localhost:8000/api/v1/latex-from-image?user_id=${userId}`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json();
                console.error("Vision API Error:", errData);
                throw new Error(errData.detail || "Analysis failed");
            }

            const data = await res.json();
            console.log("Raw Vision Response:", data);

            // Client-side Cleanup (Failsafe)
            let cleanLatex = (data.latex || "").trim();

            // 1. Strip $$ wrappers
            cleanLatex = cleanLatex.replace(/^\s*\$\$|\$\$\s*$/g, "");
            cleanLatex = cleanLatex.replace(/^\s*\$|\$\s*$/g, "");
            cleanLatex = cleanLatex.replace(/^\\\[|\\\]$/g, "");

            // 2. Normalize whitespace (tabs -> spaces, multiple spaces -> single)
            cleanLatex = cleanLatex
                .replace(/\\t/g, " ")
                .replace(/\t/g, " ")
                .replace(/[ ]{2,}/g, " ")
                .trim();

            console.log("Cleaned LaTeX:", cleanLatex);

            // Step 3: Success
            setProgressStep(3); // Done
            clearInterval(timer);

            setQuery(cleanLatex);
            if (mathInputRef.current) {
                mathInputRef.current.setValue(cleanLatex);
            }
            setOcrConfidence(0.99);

            // Small delay to show "Done" state
            setTimeout(() => {
                setWorkflowStage('review');
                setActiveTab('text'); // Switch to editor
            }, 800);

        } catch (e) {
            console.error("Analysis error", e);
            alert("Analysis failed. Please check your connection.");
            clearInterval(timer);
            setWorkflowStage('input');
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            processFile(e.target.files[0]);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            processFile(e.dataTransfer.files[0]);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const resetWorkflow = () => {
        setWorkflowStage('input');
        setCapturedImage(null);
        setCroppedImage(null);
        setQuery("");
        setProgressStep(0);
        if (mathInputRef.current) mathInputRef.current.setValue("");
    };

    const handleSolve = async () => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            // For demo purposes, if no user is logged in, just go to demo
            // router.push("/login"); 
            // return;
        }

        setIsSolving(true);

        // SIMULATION MODE: Directly route to the demo session
        // In a real app, this would call the API which would use the strict JSON prompt
        setTimeout(() => {
            setIsSolving(false);
            router.push(`/chat/demo-1`);
        }, 1500);
    };

    return (
        <div className="bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-5xl mx-auto px-4 py-8 md:py-12">
                {/* Page Heading */}
                <div className="mb-8">
                    <h1 className="text-4xl font-black tracking-tight mb-2">New Solve</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-lg">Select your preferred input method and define the context for the best tutor results.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    {/* Main Interaction Area */}
                    <div className="lg:col-span-8 space-y-6">
                        {/* Input Mode Tabs */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl shadow-black/5 border border-slate-200 dark:border-slate-800 transition-colors">
                            <div className="flex border-b border-slate-200 dark:border-slate-800">
                                <button
                                    onClick={() => setActiveTab('text')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'text' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">edit_note</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Text</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('snap')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'snap' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">add_a_photo</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Snap & Solve</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('voice')}
                                    className={`flex-1 flex flex-col items-center py-4 transition-all border-b-2 ${activeTab === 'voice' ? 'text-primary border-primary bg-primary/5' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 border-transparent'}`}
                                >
                                    <span className="material-symbols-outlined mb-1">mic</span>
                                    <span className="text-xs font-bold uppercase tracking-wider">Voice</span>
                                </button>
                            </div>

                            {/* Tab Content */}
                            <div className="p-6">
                                {activeTab === 'snap' && (
                                    <div className="flex flex-col gap-6 relative min-h-[400px]">
                                        {/* STAGE 1: INPUT */}
                                        {workflowStage === 'input' && (
                                            <>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                    <div className="space-y-2">
                                                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Subject Area</label>
                                                        <div className="relative">
                                                            <select className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg h-12 px-4 appearance-none focus:ring-2 focus:ring-primary outline-none">
                                                                <option>Mathematics</option>
                                                                <option>Physics</option>
                                                                <option>Chemistry</option>
                                                            </select>
                                                            <span className="material-symbols-outlined absolute right-3 top-3 pointer-events-none text-slate-400">expand_more</span>
                                                        </div>
                                                    </div>
                                                    <div className="space-y-2">
                                                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Difficulty</label>
                                                        <div className="relative">
                                                            <select className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg h-12 px-4 appearance-none focus:ring-2 focus:ring-primary outline-none">
                                                                <option>High School</option>
                                                                <option>College</option>
                                                            </select>
                                                            <span className="material-symbols-outlined absolute right-3 top-3 pointer-events-none text-slate-400">expand_more</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                <label
                                                    onDrop={handleDrop}
                                                    onDragOver={handleDragOver}
                                                    className="group relative flex flex-col items-center justify-center border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl px-6 py-16 hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
                                                >
                                                    <input
                                                        type="file"
                                                        className="hidden"
                                                        onChange={handleFileSelect}
                                                        accept="image/*,application/pdf"
                                                    />
                                                    <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
                                                        <span className="material-symbols-outlined text-3xl">upload_file</span>
                                                    </div>
                                                    <h3 className="text-lg font-bold mb-1">Drag & Drop or Click</h3>
                                                    <p className="text-slate-500 dark:text-slate-400 text-center max-w-sm mb-6">
                                                        Upload an image of your math problem. Max 5MB.
                                                    </p>
                                                    <div className="flex gap-3">
                                                        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-[10px] font-bold text-slate-500 uppercase">JPG</span>
                                                        <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-[10px] font-bold text-slate-500 uppercase">PNG</span>
                                                    </div>
                                                </label>

                                                <div className="flex items-center justify-center">
                                                    <label className="flex items-center gap-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 hover:opacity-90 px-8 py-3 rounded-lg font-bold transition-all shadow-lg cursor-pointer">
                                                        <input
                                                            type="file"
                                                            className="hidden"
                                                            accept="image/*"
                                                            capture="environment"
                                                            onChange={handleFileSelect}
                                                        />
                                                        <span className="material-symbols-outlined">photo_camera</span>
                                                        <span>Snap Photo</span>
                                                    </label>
                                                </div>
                                            </>
                                        )}

                                        {/* STAGE 1.5: SELECTING (Cropper) */}
                                        {workflowStage === 'selecting' && capturedImage && (
                                            <div className="absolute inset-0 z-50">
                                                <ImageCropper
                                                    imageSrc={capturedImage}
                                                    onCancel={resetWorkflow}
                                                    onConfirm={handleCropConfirm}
                                                />
                                            </div>
                                        )}

                                        {/* STAGE 2: PROCESSING */}
                                        {workflowStage === 'processing' && (
                                            <div className="absolute inset-0 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm z-50 flex flex-col items-center justify-center rounded-xl p-8">
                                                <div className="w-full max-w-sm space-y-6 text-center">
                                                    {/* Animated Icon */}
                                                    <div className="relative size-16 mx-auto">
                                                        <div className="absolute inset-0 border-4 border-slate-100 dark:border-slate-800 rounded-full"></div>
                                                        <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                                        <div className="absolute inset-0 flex items-center justify-center">
                                                            <span className="material-symbols-outlined text-2xl text-primary font-bold">document_scanner</span>
                                                        </div>
                                                    </div>

                                                    <div className="space-y-1">
                                                        <h3 className="text-lg font-bold dark:text-white">
                                                            {PROGRESS_STEPS[progressStep]?.label || "Processing..."}
                                                        </h3>
                                                        <p className="text-xs text-slate-500">
                                                            Please wait while we analyze your image.
                                                        </p>
                                                    </div>

                                                    {/* Progress Bar */}
                                                    <div className="space-y-2">
                                                        <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                            <span>Progress</span>
                                                            <span>{PROGRESS_STEPS[progressStep]?.percent || 0}%</span>
                                                        </div>
                                                        <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full bg-primary transition-all duration-500 ease-out"
                                                                style={{ width: `${PROGRESS_STEPS[progressStep]?.percent || 0}%` }}
                                                            ></div>
                                                        </div>
                                                    </div>

                                                    {/* Long Loading Warning */}
                                                    {(processingTime > 8) && (
                                                        <div className="flex gap-2 items-center justify-center text-amber-600 dark:text-amber-400 text-xs">
                                                            <span className="material-symbols-outlined text-sm">schedule</span>
                                                            <p>Taking longer than usual...</p>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* STAGE 3: REVIEW (MANDATORY) */}
                                        {workflowStage === 'review' && (
                                            <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                                <div className="flex items-center justify-between mb-2">
                                                    <h3 className="font-bold flex items-center gap-2 text-lg">
                                                        <span className="material-symbols-outlined text-green-500">check_circle</span>
                                                        Review & OCR Check
                                                    </h3>
                                                    <button onClick={resetWorkflow} className="text-xs text-slate-500 hover:text-red-500 underline">
                                                        Retake Photo
                                                    </button>
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    {/* Left: Original Image */}
                                                    <div className="bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative group h-48 md:h-auto">
                                                        {/* Left: Original Image (Cropped) */}
                                                        <div className="bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative group h-48 md:h-auto flex items-center justify-center">
                                                            {croppedImage && (
                                                                <img
                                                                    src={croppedImage}
                                                                    alt="Original Capture"
                                                                    className="max-w-full max-h-full object-contain"
                                                                />
                                                            )}
                                                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-2 py-1 text-center">
                                                                Your Selection
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Right: Editable Math */}
                                                    <div className="flex flex-col gap-2">
                                                        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-900/30 rounded-lg p-3 flex justify-between items-center">
                                                            <span className="text-xs font-bold text-green-700 dark:text-green-300 uppercase tracking-wider">
                                                                AI Confidence
                                                            </span>
                                                            <span className="font-mono font-bold text-green-600 dark:text-green-400">
                                                                {(ocrConfidence * 100).toFixed(0)}%
                                                            </span>
                                                        </div>

                                                        <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">
                                                            Detected Math (Editable)
                                                        </div>
                                                        <div className="relative border border-primary ring-2 ring-primary/20 rounded-xl bg-white dark:bg-slate-900 overflow-hidden shadow-lg min-h-[120px] flex flex-col">
                                                            <div className="flex-1 p-2">
                                                                <MathInput
                                                                    ref={mathInputRef}
                                                                    value={query}
                                                                    onChange={setQuery}
                                                                    onEnter={handleSolve}
                                                                />
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 p-3 rounded-lg text-xs text-amber-800 dark:text-amber-200 flex gap-2">
                                                    <span className="material-symbols-outlined text-sm">info</span>
                                                    <span>Please verify symbols (exponents, minus signs) match your image before solving.</span>
                                                </div>

                                                <button
                                                    onClick={handleSolve}
                                                    className="w-full bg-primary hover:bg-blue-700 text-white py-4 rounded-xl font-bold text-lg shadow-xl shadow-primary/20 flex items-center justify-center gap-2 transition-all hover:scale-[1.02]"
                                                >
                                                    <span>Confirm & Solve</span>
                                                    <span className="material-symbols-outlined">arrow_forward</span>
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                )}
                                {activeTab === 'text' && (
                                    <div className="flex flex-col gap-6 relative">
                                        {/* 2. Visual Math Editor Layout */}

                                        {/* Mode Bar */}
                                        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                                            {MODES.map(mode => (
                                                <button
                                                    key={mode.id}
                                                    onClick={() => setActiveMode(mode.id === activeMode ? null : mode.id)}
                                                    className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all border ${activeMode === mode.id
                                                        ? 'bg-primary text-white border-primary shadow-lg shadow-primary/25'
                                                        : 'bg-white dark:bg-slate-900 text-slate-500 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                        }`}
                                                >
                                                    {mode.label}
                                                </button>
                                            ))}
                                        </div>

                                        {/* Input Area with Dropdown Anchor */}
                                        <div className="relative group z-10">
                                            <div className={`bg-white dark:bg-slate-900 border rounded-xl transition-all shadow-sm flex flex-col min-h-[150px] ${activeMode ? 'border-primary ring-1 ring-primary' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                                }`}>

                                                {/* Suggestions Dropdown (Combobox) */}
                                                {activeMode && (
                                                    <div className="absolute top-full left-0 right-0 mt-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden z-50">
                                                        <div className="bg-slate-50 dark:bg-slate-800/50 px-4 py-2 border-b border-slate-100 dark:border-slate-800 text-xs font-bold text-slate-500 uppercase tracking-widest flex justify-between">
                                                            <span>{MODES.find(m => m.id === activeMode)?.label} Templates</span>
                                                            <span className="text-[10px]">Select to insert</span>
                                                        </div>
                                                        <div className="max-h-64 overflow-y-auto p-1">
                                                            {MODES.find(m => m.id === activeMode)?.suggestions.map((suggestion, idx) => (
                                                                <button
                                                                    key={idx}
                                                                    onClick={() => handleSuggestionClick(suggestion)}
                                                                    className="w-full text-left px-4 py-3 rounded-lg hover:bg-primary/5 hover:text-primary dark:hover:bg-primary/10 transition-colors flex items-center gap-3 group/item"
                                                                >
                                                                    <span className="w-8 h-8 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 group-hover/item:text-primary transition-colors text-xs font-mono">
                                                                        TeX
                                                                    </span>
                                                                    <div className="flex-1">
                                                                        <span
                                                                            className="font-medium text-slate-700 dark:text-slate-200"
                                                                            dangerouslySetInnerHTML={{
                                                                                __html: katex.renderToString(suggestion.title, {
                                                                                    throwOnError: false,
                                                                                    displayMode: false
                                                                                })
                                                                            }}
                                                                        />
                                                                    </div>
                                                                    <span className="material-symbols-outlined text-slate-300 group-hover/item:text-primary text-sm opacity-0 group-hover/item:opacity-100 transition-all">
                                                                        arrow_forward
                                                                    </span>
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                <MathInput
                                                    ref={mathInputRef}
                                                    value={query}
                                                    onChange={setQuery}
                                                    onEnter={handleSolve}
                                                    className="flex-1 p-2"
                                                />

                                                {/* Action Bar inside Input */}
                                                <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 rounded-b-xl">
                                                    <div className="flex items-center gap-2 text-xs text-slate-400">
                                                        <span className="material-symbols-outlined text-sm">keyboard</span>
                                                        <span>Math Mode Active</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={handleClear}
                                                            className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                                                        >
                                                            <span className="material-symbols-outlined text-sm">backspace</span>
                                                            Clear
                                                        </button>
                                                        <button
                                                            onClick={handleSolve}
                                                            disabled={isSolving || !query.trim()}
                                                            className="flex items-center gap-2 bg-primary hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-bold transition-all shadow-lg shadow-primary/25 text-sm"
                                                        >
                                                            {isSolving ? 'Solving...' : 'Solve'}
                                                            <span className="material-symbols-outlined text-sm">auto_awesome</span>
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {activeTab === 'voice' && (
                                    <div className="p-8 text-center text-slate-500">
                                        Voice input mode...
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Math Preview Section (Mock) */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
                            <div className="flex items-center justify-between mb-4">
                                <h4 className="font-bold flex items-center gap-2 text-slate-900 dark:text-slate-100">
                                    <span className="material-symbols-outlined text-primary">function</span>
                                    Live Math Preview
                                </h4>
                                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">LaTeX Engine v2.4</span>
                            </div>
                            <div className="w-full h-32 math-preview-bg dark:bg-slate-800/50 rounded-lg flex items-center justify-center border border-slate-100 dark:border-slate-800">
                                <p className="text-slate-400 italic text-sm">Waiting for input...</p>
                            </div>
                        </div>
                    </div>

                    {/* Sidebar */}
                    <div className="lg:col-span-4 space-y-6">
                        {/* Tips Sidebar */}
                        <div className="bg-primary/5 border border-primary/20 rounded-xl p-6">
                            <h3 className="text-primary font-bold flex items-center gap-2 mb-4">
                                <span className="material-symbols-outlined">lightbulb</span>
                                Good Photo Tips
                            </h3>
                            <ul className="space-y-4">
                                <li className="flex gap-3">
                                    <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Ensure good lighting.</strong> Avoid shadows covering the equations or variables.</p>
                                </li>
                                <li className="flex gap-3">
                                    <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Focus on one problem.</strong> Crop the image to show only the relevant task.</p>
                                </li>
                                <li className="flex gap-3">
                                    <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Include diagrams.</strong> If the problem references a graph, make sure it's in the shot.</p>
                                </li>
                            </ul>
                        </div>

                        {/* Recent Solutions */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white">Recent History</h3>
                                <a className="text-primary text-xs font-semibold hover:underline" href="#">View All</a>
                            </div>
                            <div className="space-y-3">
                                {history.length === 0 ? (
                                    <p className="text-sm text-slate-500 italic">No history found.</p>
                                ) : (
                                    history.map((session) => (
                                        <div
                                            key={session.id}
                                            onClick={() => router.push(`/chat/${session.id}`)}
                                            className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 hover:border-primary/30 transition-colors cursor-pointer group"
                                        >
                                            <p className="text-xs font-bold text-primary mb-1 uppercase tracking-tighter">Session #{session.id}</p>
                                            <p className="text-sm font-medium line-clamp-1 mb-2 text-slate-900 dark:text-slate-200">{session.title}</p>
                                            <div className="flex justify-between items-center text-[10px] text-slate-400 font-medium">
                                                <span>{new Date(session.created_at).toLocaleDateString()}</span>
                                                <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Pro Callout */}
                        <div className="relative overflow-hidden bg-slate-900 rounded-xl p-6 text-white group">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/40 transition-colors"></div>
                            <div className="relative z-10">
                                <h4 className="text-lg font-bold mb-2">uask Pro</h4>
                                <p className="text-slate-400 text-sm mb-4">Unlock unlimited step-by-step solutions and 1-on-1 expert tutor sessions.</p>
                                <button className="w-full bg-white text-slate-900 font-bold py-2.5 rounded-lg text-sm hover:bg-slate-100 transition-colors">
                                    Upgrade Now
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            <footer className="max-w-7xl mx-auto px-4 py-8 border-t border-slate-200 dark:border-slate-800 text-center">
                <p className="text-slate-400 text-xs font-medium">© 2024 uask.ai - Intelligent Math & Physics Tutoring Platform</p>
            </footer>
        </div>
    );
}
