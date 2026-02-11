"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MathRenderer from "@/components/math/MathJaxRenderer";

type CaseItem = {
    id: string;
    label: string;
    mode: "prose" | "inline" | "block";
    content: string;
};

const CASES: CaseItem[] = [
    { id: "p1", label: "Inline basics", mode: "prose", content: "Let \\(x=2\\) then \\(x^2=4\\)." },
    { id: "p2", label: "Inline with words", mode: "prose", content: "In 2026, if \\(x=5\\), then we get \\(2x=10\\)." },
    { id: "p3", label: "Currency stays text", mode: "prose", content: "The price is $5 today, not math." },
    { id: "p4", label: "Safe $...$ inline", mode: "prose", content: "Legacy: $x+1$ becomes inline." },
    { id: "p5", label: "Legacy $$ block", mode: "prose", content: "Legacy block:\n$$x^2 + 3x + 2 = 0$$\nDone." },
    { id: "p6", label: "Fenced latex block", mode: "prose", content: "Block:\n```latex\nx+3=5\n```\nEnd." },
    { id: "p7", label: "Numbers between words", mode: "prose", content: "Step 2 uses \\(x=7\\) then move on." },
    { id: "p8", label: "Inline fractions", mode: "prose", content: "Compute \\(\\frac{2}{3}x\\) and \\(\\frac{1}{2}x\\)." },
    { id: "p9", label: "Inline trig", mode: "prose", content: "We know \\(\\sin^2(x)+\\cos^2(x)=1\\)." },
    { id: "p10", label: "Inline logs", mode: "prose", content: "Use \\(\\ln(x)\\) and \\(\\log_{10}(x)\\)." },
    { id: "p11", label: "Inline inequalities", mode: "prose", content: "Solve \\(x \\ge 3\\) and \\(x \\le 9\\)." },
    { id: "p12", label: "Inline sets", mode: "prose", content: "Let \\(x \\in \\mathbb{R}\\)." },
    { id: "p13", label: "Inline summation", mode: "prose", content: "Sum \\(\\sum_{k=1}^{n} k\\)." },
    { id: "p14", label: "Inline limit", mode: "prose", content: "Limit \\(\\lim_{x\\to 0} \\frac{\\sin x}{x}\\)." },
    { id: "p15", label: "Inline integral", mode: "prose", content: "Area \\(\\int_0^1 x^2 dx\\)." },
    { id: "p16", label: "Inline vectors", mode: "prose", content: "Vector \\(\\vec{v}\\) has magnitude \\(\\|v\\|\\)." },
    { id: "p17", label: "Inline matrix", mode: "prose", content: "Matrix \\(\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}\\)." },
    { id: "p18", label: "Inline piecewise", mode: "prose", content: "Piecewise \\(f(x)=\\begin{cases}x^2&x\\ge0\\\\-x&x<0\\end{cases}\\)." },
    { id: "p19", label: "Inline exponents", mode: "prose", content: "Compute \\(e^{\\ln x}=x\\)." },
    { id: "p20", label: "Inline radicals", mode: "prose", content: "Simplify \\(\\sqrt{50x^2}\\)." },
    { id: "p21", label: "Inline complex", mode: "prose", content: "Let \\(z = a+bi\\)." },
    { id: "p22", label: "Inline binomial", mode: "prose", content: "Use \\(\\binom{n}{k}\\)." },
    { id: "p23", label: "Inline absolute", mode: "prose", content: "Solve \\(|2x-3|=7\\)." },
    { id: "p24", label: "Inline series", mode: "prose", content: "Series \\(\\sum_{n=0}^{\\infty} \\frac{1}{2^n}\\)." },
    { id: "p25", label: "Inline greek", mode: "prose", content: "Angle \\(\\theta\\) in radians." },

    { id: "b1", label: "Aligned system", mode: "block", content: "\\begin{aligned}x+3 &= 5 \\\\ x &= 2\\end{aligned}" },
    { id: "b2", label: "Cases", mode: "block", content: "\\begin{cases}x^2 & x \\ge 0 \\\\ -x & x < 0\\end{cases}" },
    { id: "b3", label: "Matrix pmatrix", mode: "block", content: "\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}" },
    { id: "b4", label: "Matrix bmatrix", mode: "block", content: "\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}" },
    { id: "b5", label: "Array", mode: "block", content: "\\begin{array}{cc}1&2\\\\3&4\\end{array}" },
    { id: "b6", label: "Fraction", mode: "block", content: "\\frac{a+b}{c+d}" },
    { id: "b7", label: "Integral", mode: "block", content: "\\int_0^\\infty e^{-x} dx" },
    { id: "b8", label: "Summation", mode: "block", content: "\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}" },
    { id: "b9", label: "Limit", mode: "block", content: "\\lim_{x\\to 0} \\frac{\\sin x}{x} = 1" },
    { id: "b10", label: "Logarithms", mode: "block", content: "\\log_a(xy)=\\log_a x+\\log_a y" },
    { id: "b11", label: "Trig identity", mode: "block", content: "\\sin^2 x + \\cos^2 x = 1" },
    { id: "b12", label: "Inequalities", mode: "block", content: "x^2 - 4x + 1 \\ge 0" },
    { id: "b13", label: "Piecewise", mode: "block", content: "f(x)=\\begin{cases}x&x\\ge0\\\\-x&x<0\\end{cases}" },
    { id: "b14", label: "System", mode: "block", content: "\\begin{aligned}2x+3y&=7\\\\x-y&=1\\end{aligned}" },
    { id: "b15", label: "Vector", mode: "block", content: "\\vec{v} = \\langle 1,2,3 \\rangle" },
    { id: "b16", label: "Determinant", mode: "block", content: "\\det\\begin{pmatrix}a&b\\\\c&d\\end{pmatrix}=ad-bc" },
    { id: "b17", label: "Quadratic", mode: "block", content: "x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}" },
    { id: "b18", label: "Exponential", mode: "block", content: "e^{i\\pi}+1=0" },
    { id: "b19", label: "Binomial", mode: "block", content: "(a+b)^n=\\sum_{k=0}^n \\binom{n}{k} a^{n-k} b^k" },
    { id: "b20", label: "Complex", mode: "block", content: "(a+bi)(c+di)=(ac-bd)+i(ad+bc)" },

    { id: "i1", label: "Inline raw latex", mode: "inline", content: "x^2 + y^2 = z^2" },
    { id: "i2", label: "Inline sqrt", mode: "inline", content: "\\sqrt{2x+3}" },
    { id: "i3", label: "Inline fraction", mode: "inline", content: "\\frac{1}{1+x}" },
    { id: "i4", label: "Inline sum", mode: "inline", content: "\\sum_{k=1}^{n} k" },
    { id: "i5", label: "Inline limit", mode: "inline", content: "\\lim_{x\\to 0} \\frac{\\sin x}{x}" },
    { id: "i6", label: "Inline matrix", mode: "inline", content: "\\begin{pmatrix}1&0\\\\0&1\\end{pmatrix}" },
    { id: "i7", label: "Inline cases", mode: "inline", content: "\\begin{cases}1&x>0\\\\0&x=0\\\\-1&x<0\\end{cases}" },
    { id: "i8", label: "Inline inequality", mode: "inline", content: "x \\le y" },
    { id: "i9", label: "Inline trig", mode: "inline", content: "\\tan(x)=\\frac{\\sin x}{\\cos x}" },
    { id: "i10", label: "Inline log", mode: "inline", content: "\\log_{2}(8)=3" },

    { id: "p26", label: "Long prose", mode: "prose", content: "This is a longer paragraph that includes inline math such as \\(a^2+b^2=c^2\\) and a block:\n\\[\\int_0^1 x^2 dx = \\frac{1}{3}\\]\nThe text continues after the block without losing spaces." },
    { id: "p27", label: "Stray dollar", mode: "prose", content: "Stray dollar $ should be escaped." },
    { id: "p28", label: "Nested text", mode: "prose", content: "Sentence: \"If \\(x=4\\), then \\(x+1=5\\).\"" },
    { id: "p29", label: "Inline with punctuation", mode: "prose", content: "Compute \\(x=1\\), then proceed." },
    { id: "p30", label: "Inline before newline", mode: "prose", content: "First line \\(x=1\\)\nSecond line continues." },
];

export default function MathRenderTestPage() {
    const router = useRouter();
    const [isAuthorized] = useState(() => {
        if (typeof window === "undefined") return false;
        return localStorage.getItem("user_role") === "admin";
    });

    useEffect(() => {
        if (isAuthorized) return;
        const role = localStorage.getItem("user_role");
        if (role !== "admin") {
            router.push("/login");
        }
    }, [isAuthorized, router]);

    if (!isAuthorized) return null;

    return (
        <div className="min-h-screen bg-background-light dark:bg-background-dark px-6 py-10">
            <div className="max-w-5xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Math Render Regression Harness</h1>
                        <p className="text-sm text-slate-500 dark:text-slate-400">Admin-only route for validating tricky math/prose combinations.</p>
                    </div>
                    <span className="text-xs font-bold uppercase tracking-widest text-primary">/dev/math-render-test</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {CASES.map((item) => (
                        <div key={item.id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">{item.label}</span>
                                <span className="text-[10px] font-mono text-slate-400">{item.mode}</span>
                            </div>
                            <div className="text-sm text-slate-900 dark:text-slate-200">
                                <MathRenderer content={item.content} mode={item.mode} dynamic />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
