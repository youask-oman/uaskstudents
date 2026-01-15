
import { describe, it, expect } from './test-utils';

// ============================================================================
// EXTRACTED VALIDATION LOGIC FROM src/app/solve/page.tsx
// ============================================================================

const validateMathQuery = (value: string): string | null => {
    const normalized = value.trim().toLowerCase();
    if (!normalized) return "Please enter a math question.";
    if (normalized.length < 3) return "Please enter at least 3 characters.";

    const badWords = [
        "fuck", "fucking", "shit", "shitty", "bitch", "asshole", "bastard",
        "dick", "cock", "pussy", "cunt", "nigger", "faggot", "slut", "whore",
        "motherfucker", "sex", "sexual", "porn", "porno", "pornography",
        "rape", "rapist", "cum", "ejaculate", "orgasm", "blowjob", "handjob",
        "anal", "penis", "vagina", "boobs", "tits", "nude", "nudes", "naked"
    ];
    if (badWords.some(word => new RegExp(`\\b${word}\\b`, "i").test(normalized))) {
        return "Inappropriate language detected. Please rephrase.";
    }

    const forbiddenPatterns = [
        /<script/i,
        /<\/\w/i,
        /\bimport\s+\w+/i,
        /\bfrom\s+[\w\.]+\s+import\b/i,
        /require\(/i,
        /eval\(/i,
        /exec\(/i,
        /subprocess/i,
        /system\(/i,
        /\bcat\s/i,
        /\bls\s/i,
        /\bdir\s/i,
        /\bchmod\s/i,
        /\bchown\s/i,
        /curl\s/i,
        /wget\s/i,
        /powershell/i,
        /cmd\.exe/i,
        /rm\s/i,
        /del\s/i,
        /drop\s+table/i,
        /insert\s+into/i,
        /update\s+\w+/i,
        /delete\s+from/i,
        /\bselect\s+.*\bfrom\b/i,
        /union\s+select/i,
        /https?:\/\//i,
        /\$\{/i,
        /\{\{/i
    ];
    if (forbiddenPatterns.some(pattern => pattern.test(normalized))) {
        return "Input blocked. Please enter a valid math question.";
    }

    const mathHints = [
        /\d/,
        /[=<>+\-*/^]/,
        /\\(frac|sqrt|int|sum|lim|log|sin|cos|tan|theta|pi|alpha|beta|gamma|cdot|times)/i,
        /\b(solve|simplify|factor|expand|evaluate|derivative|integral|integrate|limit|graph|plot|domain|range|root|roots|intercept|slope|equation|function|probability|matrix|vector|geometry|algebra|calculus)\b/i
    ];
    if (!mathHints.some(pattern => pattern.test(normalized))) {
        return "Input must be a math question.";
    }

    return null; // OK
};

// ============================================================================
// ALL TEMPLATES (Copied from src/lib/modes.ts)
// ============================================================================

interface Suggestion {
    title: string;
    latex: string;
}

interface EditorMode {
    id: string;
    label: string;
    suggestions: Suggestion[];
}

const MODES: EditorMode[] = [
    {
        id: 'simplify',
        label: 'Simplify',
        suggestions: [
            { title: '\\text{Simplify } x^0', latex: '\\text{Simplify } x^0' },
            { title: '\\text{Simplify } (x^2 - 1)/(x - 1)', latex: '\\text{Simplify } \\frac{x^2 - 1}{x - 1}' },
            { title: '\\text{Simplify } (2x^3y^2)/(4xy)', latex: '\\text{Simplify } \\frac{2x^3y^{2}}{4xy}' },
            { title: '\\text{Simplify } x^5/x^2', latex: '\\text{Simplify } \\frac{x^5}{x^2}' },
            { title: '\\text{Simplify } \\sqrt{72}', latex: '\\text{Simplify } \\sqrt{72}' },
            { title: '\\text{Simplify } \\sqrt{50x^2}', latex: '\\text{Simplify } \\sqrt{50x^2}' },
            { title: '\\text{Simplify } (x^2)^{1/2}', latex: '\\text{Simplify } (x^2)^{1/2}' },
            { title: '\\text{Simplify } \\ln(e^x)', latex: '\\text{Simplify } \\ln(e^x)' },
            { title: '\\text{Simplify } e^{\\ln(x)}', latex: '\\text{Simplify } e^{\\ln(x)}' },
            { title: '\\text{Simplify } \\sin^2(x) + \\cos^2(x)', latex: '\\text{Simplify } \\sin^2(x) + \\cos^2(x)' }
        ]
    },
    {
        id: 'solve_for',
        label: 'Solve For',
        suggestions: [
            { title: '\\text{Solve for x, } 2x + 7 = 19', latex: '\\text{Solve for } x, 2x + 7 = 19' },
            { title: '\\text{Solve for x, } 3(x - 2) = 15', latex: '\\text{Solve for } x, 3(x - 2) = 15' },
            { title: '\\text{Solve for x, } x^2 - 5x + 6 = 0', latex: '\\text{Solve for } x, x^2 - 5x + 6 = 0' },
            { title: '\\text{Solve for x, } (x + 1)/(x - 2) = 3', latex: '\\text{Solve for } x, \\frac{x + 1}{x - 2} = 3' },
            { title: '\\text{Solve for x, } \\sqrt{x + 5} = 4', latex: '\\text{Solve for } x, \\sqrt{x + 5} = 4' },
            { title: '\\text{Solve for x, } \\sqrt{x + 3} + \\sqrt{x} = 5', latex: '\\text{Solve for } x, \\sqrt{x + 3} + \\sqrt{x} = 5' },
            { title: '\\text{Solve for x, } 2^x = 16', latex: '\\text{Solve for } x, 2^x = 16' },
            { title: '\\text{Solve for x, } \\ln(x) = 2', latex: '\\text{Solve for } x, \\ln(x) = 2' },
            { title: '\\text{Solve for x, } |2x - 3| = 7', latex: '\\text{Solve for } x, |2x - 3| = 7' },
            { title: '\\text{Solve for x, } x^2 - 4x > 0', latex: '\\text{Solve for } x, x^2 - 4x > 0' }
        ]
    },
    {
        id: 'inverse',
        label: 'Inverse',
        suggestions: [
            { title: '\\text{inverse } f(x) = 2x + 3', latex: '\\text{inverse } f(x) = 2x + 3' },
            { title: '\\text{inverse } f(x) = (x - 1)/(x + 2)', latex: '\\text{inverse } f(x) = \\frac{x - 1}{x + 2}' },
            { title: '\\text{inverse } f(x) = x^2', latex: '\\text{inverse } f(x) = x^2' },
            { title: '\\text{inverse } f(x) = \\sqrt{x + 3}', latex: '\\text{inverse } f(x) = \\sqrt{x + 3}' },
            { title: '\\text{inverse } f(x) = e^x', latex: '\\text{inverse } f(x) = e^x' },
            { title: '\\text{inverse } f(x) = \\ln(x)', latex: '\\text{inverse } f(x) = \\ln(x)' },
            { title: '\\text{inverse } \\sin(x)', latex: '\\text{inverse } \\sin(x)' },
            { title: '\\text{inverse } \\tan(x)', latex: '\\text{inverse } \\tan(x)' },
            { title: '\\text{inverse } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{inverse } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}' },
            { title: '\\text{inverse laplace } 1/(s(s+2))', latex: '\\text{inverse laplace } \\frac{1}{s(s+2)}' }
        ]
    },
    {
        id: 'tangent',
        label: 'Tangent',
        suggestions: [
            { title: '\\text{tangent of } f(x) = x^2, x = 1', latex: '\\text{tangent of } f(x) = x^2, x = 1' },
            { title: '\\text{tangent of } f(x) = x^3, x = 2', latex: '\\text{tangent of } f(x) = x^3, x = 2' },
            { title: '\\text{tangent of } \\sin(x), x = 0', latex: '\\text{tangent of } \\sin(x), x = 0' },
            { title: '\\text{tangent of } \\cos(x), x = 0', latex: '\\text{tangent of } \\cos(x), x = 0' },
            { title: '\\text{tangent of } e^x, x = 0', latex: '\\text{tangent of } e^x, x = 0' },
            { title: '\\text{tangent of } \\ln(x), x = 1', latex: '\\text{tangent of } \\ln(x), x = 1' },
            { title: '\\text{tangent of } 1/x, x = 1', latex: '\\text{tangent of } 1/x, x = 1' },
            { title: '\\text{tangent of } \\sqrt{x}, x = 4', latex: '\\text{tangent of } \\sqrt{x}, x = 4' },
            { title: '\\text{tangent of } f(x) = x^2 + 2x + 1, x = -1', latex: '\\text{tangent of } f(x) = x^2 + 2x + 1, x = -1' },
            { title: '\\text{tangent of } f(x) = (x^2 + 1)/(x - 1), x = 2', latex: '\\text{tangent of } f(x) = \\frac{x^2 + 1}{x - 1}, x = 2' }
        ]
    },
    {
        id: 'line',
        label: 'Line',
        suggestions: [
            { title: '\\text{line } (0, 0), (2, 3)', latex: '\\text{line } (0, 0), (2, 3)' },
            { title: '\\text{line } (1, 2), (4, 2)', latex: '\\text{line } (1, 2), (4, 2)' },
            { title: '\\text{line } (2, 5), (2, -1)', latex: '\\text{line } (2, 5), (2, -1)' },
            { title: '\\text{line } (-1, 3), (2, -3)', latex: '\\text{line } (-1, 3), (2, -3)' },
            { title: '\\text{line } (3, -2), (6, 4)', latex: '\\text{line } (3, -2), (6, 4)' },
            { title: '\\text{line } (-2, -1), (4, 5)', latex: '\\text{line } (-2, -1), (4, 5)' },
            { title: '\\text{line } (-3, 0), (0, 6)', latex: '\\text{line } (-3, 0), (0, 6)' },
            { title: '\\text{line } (1, 1), (2, 4)', latex: '\\text{line } (1, 1), (2, 4)' },
            { title: '\\text{line } (2, 3), (5, 9)', latex: '\\text{line } (2, 3), (5, 9)' },
            { title: '\\text{line } (-4, 2), (1, -3)', latex: '\\text{line } (-4, 2), (1, -3)' }
        ]
    },
    {
        id: 'area',
        label: 'Area',
        suggestions: [
            { title: '\\text{area } x^2 \\text{ from } 0 \\text{ to } 2', latex: '\\text{area } x^2 \\text{ from } 0 \\text{ to } 2' },
            { title: '\\text{area } \\sin(x) \\text{ from } 0 \\text{ to } \\pi', latex: '\\text{area } \\sin(x) \\text{ from } 0 \\text{ to } \\pi' },
            { title: '\\text{area } x \\text{ from } 0 \\text{ to } 5', latex: '\\text{area } x \\text{ from } 0 \\text{ to } 5' },
            { title: '\\text{area } (x^3 - x) \\text{ from } -1 \\text{ to } 1', latex: '\\text{area } (x^{3} - x) \\text{ from } -1 \\text{ to } 1' },
            { title: '\\text{area } e^x \\text{ from } 0 \\text{ to } 1', latex: '\\text{area } e^x \\text{ from } 0 \\text{ to } 1' },
            { title: '\\text{area } |x| \\text{ from } -2 \\text{ to } 2', latex: '\\text{area } |x| \\text{ from } -2 \\text{ to } 2' },
            { title: '\\text{area } (x^2 + 1) \\text{ from } -1 \\text{ to } 1', latex: '\\text{area } (x^{2} + 1) \\text{ from } -1 \\text{ to } 1' },
            { title: '\\text{area } (2x + 3) \\text{ from } 1 \\text{ to } 4', latex: '\\text{area } (2x + 3) \\text{ from } 1 \\text{ to } 4' },
            { title: '\\text{area } \\cos(x) \\text{ from } 0 \\text{ to } \\pi/2', latex: '\\text{area } \\cos(x) \\text{ from } 0 \\text{ to } \\pi/2' },
            { title: '\\text{area } (1/x) \\text{ from } 1 \\text{ to } 4', latex: '\\text{area } (1/x) \\text{ from } 1 \\text{ to } 4' }
        ]
    },
    {
        id: 'asymptotes',
        label: 'Asymptotes',
        suggestions: [
            { title: '\\text{asymptotes } (x+1)/(x-2)', latex: '\\text{asymptotes } \\frac{x+1}{x-2}' },
            { title: '\\text{asymptotes } (2x^2+3)/(x-1)', latex: '\\text{asymptotes } \\frac{2x^2+3}{x-1}' },
            { title: '\\text{asymptotes } 1/(x^2)', latex: '\\text{asymptotes } \\frac{1}{x^2}' },
            { title: '\\text{asymptotes } (x^2+1)/(x)', latex: '\\text{asymptotes } \\frac{x^2+1}{x}' },
            { title: '\\text{asymptotes } (x^2-4)/(x-2)', latex: '\\text{asymptotes } \\frac{x^2-4}{x-2}' },
            { title: '\\text{asymptotes } (3x-1)/(x+5)', latex: '\\text{asymptotes } \\frac{3x-1}{x+5}' },
            { title: '\\text{asymptotes } (x^2)/(x^2+1)', latex: '\\text{asymptotes } \\frac{x^2}{x^2+1}' },
            { title: '\\text{asymptotes } (x^3)/(x^2+1)', latex: '\\text{asymptotes } \\frac{x^3}{x^2+1}' },
            { title: '\\text{asymptotes } 1/(x-3)^2', latex: '\\text{asymptotes } \\frac{1}{(x-3)^2}' },
            { title: '\\text{asymptotes } (x^2+2x+1)/(x^2-1)', latex: '\\text{asymptotes } \\frac{x^2+2x+1}{x^2-1}' }
        ]
    },
    {
        id: 'critical_points',
        label: 'Critical Points',
        suggestions: [
            { title: '\\text{critical points } x^3 - 3x', latex: '\\text{critical points } x^3 - 3x' },
            { title: '\\text{critical points } x^4 - 4x^2', latex: '\\text{critical points } x^4 - 4x^2' },
            { title: '\\text{critical points } x^2 + 4x + 1', latex: '\\text{critical points } x^2 + 4x + 1' },
            { title: '\\text{critical points } \\sin(x)', latex: '\\text{critical points } \\sin(x)' },
            { title: '\\text{critical points } \\cos(x)', latex: '\\text{critical points } \\cos(x)' },
            { title: '\\text{critical points } e^x - x', latex: '\\text{critical points } e^x - x' },
            { title: '\\text{critical points } \\ln(x) - x', latex: '\\text{critical points } \\ln(x) - x' },
            { title: '\\text{critical points } x/(x^2+1)', latex: '\\text{critical points } \\frac{x}{x^2+1}' },
            { title: '\\text{critical points } \\sqrt{x} \\; (x \\ge 0)', latex: '\\text{critical points } \\sqrt{x} \\text{ on } x \\ge 0' },
            { title: '\\text{critical points } (x^2+1)/(x-1)', latex: '\\text{critical points } \\frac{x^2+1}{x-1}' }
        ]
    },
    {
        id: 'derivative',
        label: 'Derivative',
        suggestions: [
            { title: '\\text{derivative } x^2', latex: '\\text{derivative } x^2' },
            { title: '\\text{derivative } x^3 - 5x + 1', latex: '\\text{derivative } x^3 - 5x + 1' },
            { title: '\\text{derivative } \\sqrt{x}', latex: '\\text{derivative } \\sqrt{x}' },
            { title: '\\text{derivative } 1/x', latex: '\\text{derivative } \\frac{1}{x}' },
            { title: '\\text{derivative } (x^2 + 1)/(x - 1)', latex: '\\text{derivative } \\frac{x^2 + 1}{x - 1}' },
            { title: '\\text{derivative } \\sin(x)', latex: '\\text{derivative } \\sin(x)' },
            { title: '\\text{derivative } \\cos(x)', latex: '\\text{derivative } \\cos(x)' },
            { title: '\\text{derivative } e^x', latex: '\\text{derivative } e^x' },
            { title: '\\text{derivative } \\ln(x)', latex: '\\text{derivative } \\ln(x)' },
            { title: '\\text{derivative } (x^2)\\sin(x)', latex: '\\text{derivative } (x^2)\\sin(x)' }
        ]
    },
    {
        id: 'domain',
        label: 'Domain',
        suggestions: [
            { title: '\\text{domain } \\sqrt{x-3}', latex: '\\text{domain } \\sqrt{x-3}' },
            { title: '\\text{domain } 1/(x-2)', latex: '\\text{domain } \\frac{1}{x-2}' },
            { title: '\\text{domain } \\ln(x)', latex: '\\text{domain } \\ln(x)' },
            { title: '\\text{domain } \\ln(x-1)', latex: '\\text{domain } \\ln(x-1)' },
            { title: '\\text{domain } 1/\\sqrt{x+2}', latex: '\\text{domain } \\frac{1}{\\sqrt{x+2}}' },
            { title: '\\text{domain } (x+1)/(x^2-9)', latex: '\\text{domain } \\frac{x+1}{x^2-9}' },
            { title: '\\text{domain } \\sqrt{x^2-4}', latex: '\\text{domain } \\sqrt{x^2-4}' },
            { title: '\\text{domain } 1/(x^2+1)', latex: '\\text{domain } \\frac{1}{x^2+1}' },
            { title: '\\text{domain } (x^2+3x+2)/(x+1)', latex: '\\text{domain } \\frac{x^2+3x+2}{x+1}' },
            { title: '\\text{domain } \\tan(x)', latex: '\\text{domain } \\tan(x)' }
        ]
    },
    {
        id: 'eigenvalues',
        label: 'Eigenvalues',
        suggestions: [
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}' }
        ]
    },
    {
        id: 'eigenvectors',
        label: 'Eigenvectors',
        suggestions: [
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}' }
        ]
    },
    {
        id: 'expand',
        label: 'Expand',
        suggestions: [
            { title: '\\text{expand } (x+2)^2', latex: '\\text{expand } (x+2)^2' },
            { title: '\\text{expand } (x-3)(x+3)', latex: '\\text{expand } (x-3)(x+3)' },
            { title: '\\text{expand } (2x-1)(x+4)', latex: '\\text{expand } (2x-1)(x+4)' },
            { title: '\\text{expand } (x+1)^3', latex: '\\text{expand } (x+1)^3' },
            { title: '\\text{expand } (x-2)^3', latex: '\\text{expand } (x-2)^3' },
            { title: '\\text{expand } (x+2)(x^2-2x+4)', latex: '\\text{expand } (x+2)(x^2-2x+4)' },
            { title: '\\text{expand } (x+y)^2', latex: '\\text{expand } (x+y)^2' },
            { title: '\\text{expand } (a-b)^3', latex: '\\text{expand } (a-b)^3' },
            { title: '\\text{expand } (2x+3y)^2', latex: '\\text{expand } (2x+3y)^2' },
            { title: '\\text{expand } (x-1)(x^2+x+1)', latex: '\\text{expand } (x-1)(x^2+x+1)' }
        ]
    },
    {
        id: 'extreme_points',
        label: 'Extreme Points',
        suggestions: [
            { title: '\\text{extreme points } x^3 - 3x', latex: '\\text{extreme points } x^3 - 3x' },
            { title: '\\text{extreme points } x^4 - 4x^2', latex: '\\text{extreme points } x^4 - 4x^2' },
            { title: '\\text{extreme points } x^2 + 4x + 1', latex: '\\text{extreme points } x^2 + 4x + 1' },
            { title: '\\text{extreme points } \\sin(x) \\text{ on } [0, 2\\pi]', latex: '\\text{extreme points } \\sin(x) \\text{ on } [0, 2\\pi]' },
            { title: '\\text{extreme points } \\cos(x) \\text{ on } [0, 2\\pi]', latex: '\\text{extreme points } \\cos(x) \\text{ on } [0, 2\\pi]' },
            { title: '\\text{extreme points } e^x - x', latex: '\\text{extreme points } e^x - x' },
            { title: '\\text{extreme points } \\ln(x) - x', latex: '\\text{extreme points } \\ln(x) - x' },
            { title: '\\text{extreme points } x/(x^2+1)', latex: '\\text{extreme points } \\frac{x}{x^2+1}' },
            { title: '\\text{extreme points } -(x-2)^2 + 3', latex: '\\text{extreme points } -(x-2)^2 + 3' },
            { title: '\\text{extreme points } (x^2+1)/(x-1)', latex: '\\text{extreme points } \\frac{x^2+1}{x-1}' }
        ]
    }
];

// ============================================================================
// TESTS
// ============================================================================

export async function run() {
    console.log(`\n📦 STARTING COMPREHENSIVE TEMPLATE VALIDATION`);
    console.log(`   Validating ${MODES.length} different modes...`);

    let totalPassed = 0;
    let totalFailed = 0;

    for (const mode of MODES) {
        describe(`${mode.label} Templates`, () => {
            for (const suggestion of mode.suggestions) {
                it(`Template: ${suggestion.title}`, () => {
                    const error = validateMathQuery(suggestion.latex);
                    if (error) {
                        totalFailed++;
                        throw new Error(`FAILED: "${suggestion.latex}" => Error: ${error}`);
                    }
                    expect(error).toBe(null);
                    totalPassed++;
                });
            }
        });
    }

    console.log(`\n==================================================`);
    console.log(`SUMMARY:`);
    console.log(`✅ Passed: ${totalPassed}`);
    console.log(`❌ Failed: ${totalFailed}`);
    console.log(`==================================================\n`);

    if (totalFailed > 0) process.exit(1);
}

// Run if main
if (require.main === module) {
    run().catch(console.error);
}
