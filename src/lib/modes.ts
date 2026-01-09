export type ModeId = 'simplify' | 'solve_for' | 'inverse' | 'tangent' | 'area' | 'line' | 'asymptotes' | 'critical_points' | 'derivative' | 'domain' | 'eigenvalues' | 'eigenvectors' | 'expand' | 'extreme_points';

export interface Suggestion {
    title: string; // The specific math to show (e.g., "\sqrt{50}")
    latex: string; // What gets inserted (e.g., "\sqrt{#?}")
    insertMode?: 'replace' | 'append' | 'smart'; // How it interacts with existing input
    tags?: string[];
}

export interface EditorMode {
    id: ModeId;
    label: string;
    placeholderLatex: string; // Default starter if needed
    suggestions: Suggestion[];
}

export const MODES: EditorMode[] = [
    {
        id: 'simplify',
        label: 'Simplify',
        placeholderLatex: '',
        suggestions: [
            { title: '\\text{Simplify } x^0', latex: '\\text{Simplify } x^0', insertMode: 'replace' },
            { title: '\\text{Simplify } (x^2 - 1)/(x - 1)', latex: '\\text{Simplify } \\frac{x^2 - 1}{x - 1}', insertMode: 'replace' },
            { title: '\\text{Simplify } (2x^3y^2)/(4xy)', latex: '\\text{Simplify } \\frac{2x^3y^{2}}{4xy}', insertMode: 'replace' },
            { title: '\\text{Simplify } x^5/x^2', latex: '\\text{Simplify } \\frac{x^5}{x^2}', insertMode: 'replace' },
            { title: '\\text{Simplify } \\sqrt{72}', latex: '\\text{Simplify } \\sqrt{72}', insertMode: 'replace' },
            { title: '\\text{Simplify } \\sqrt{50x^2}', latex: '\\text{Simplify } \\sqrt{50x^2}', insertMode: 'replace' },
            { title: '\\text{Simplify } (x^2)^{1/2}', latex: '\\text{Simplify } (x^2)^{1/2}', insertMode: 'replace' },
            { title: '\\text{Simplify } \\ln(e^x)', latex: '\\text{Simplify } \\ln(e^x)', insertMode: 'replace' },
            { title: '\\text{Simplify } e^{\\ln(x)}', latex: '\\text{Simplify } e^{\\ln(x)}', insertMode: 'replace' },
            { title: '\\text{Simplify } \\sin^2(x) + \\cos^2(x)', latex: '\\text{Simplify } \\sin^2(x) + \\cos^2(x)', insertMode: 'replace' }
        ]
    },
    {
        id: 'solve_for',
        label: 'Solve For',
        placeholderLatex: '\\text{Solve for } x, ',
        suggestions: [
            { title: '\\text{Solve for x, } 2x + 7 = 19', latex: '\\text{Solve for } x, 2x + 7 = 19', insertMode: 'replace' },
            { title: '\\text{Solve for x, } 3(x - 2) = 15', latex: '\\text{Solve for } x, 3(x - 2) = 15', insertMode: 'replace' },
            { title: '\\text{Solve for x, } x^2 - 5x + 6 = 0', latex: '\\text{Solve for } x, x^2 - 5x + 6 = 0', insertMode: 'replace' },
            { title: '\\text{Solve for x, } (x + 1)/(x - 2) = 3', latex: '\\text{Solve for } x, \\frac{x + 1}{x - 2} = 3', insertMode: 'replace' },
            { title: '\\text{Solve for x, } \\sqrt{x + 5} = 4', latex: '\\text{Solve for } x, \\sqrt{x + 5} = 4', insertMode: 'replace' },
            { title: '\\text{Solve for x, } \\sqrt{x + 3} + \\sqrt{x} = 5', latex: '\\text{Solve for } x, \\sqrt{x + 3} + \\sqrt{x} = 5', insertMode: 'replace' },
            { title: '\\text{Solve for x, } 2^x = 16', latex: '\\text{Solve for } x, 2^x = 16', insertMode: 'replace' },
            { title: '\\text{Solve for x, } \\ln(x) = 2', latex: '\\text{Solve for } x, \\ln(x) = 2', insertMode: 'replace' },
            { title: '\\text{Solve for x, } |2x - 3| = 7', latex: '\\text{Solve for } x, |2x - 3| = 7', insertMode: 'replace' },
            { title: '\\text{Solve for x, } x^2 - 4x > 0', latex: '\\text{Solve for } x, x^2 - 4x > 0', insertMode: 'replace' }
        ]
    },
    {
        id: 'inverse',
        label: 'Inverse',
        placeholderLatex: '\\text{inverse of } ',
        suggestions: [
            { title: '\\text{inverse } f(x) = 2x + 3', latex: '\\text{inverse } f(x) = 2x + 3', insertMode: 'replace' },
            { title: '\\text{inverse } f(x) = (x - 1)/(x + 2)', latex: '\\text{inverse } f(x) = \\frac{x - 1}{x + 2}', insertMode: 'replace' },
            { title: '\\text{inverse } f(x) = x^2', latex: '\\text{inverse } f(x) = x^2', insertMode: 'replace' },
            { title: '\\text{inverse } f(x) = \\sqrt{x + 3}', latex: '\\text{inverse } f(x) = \\sqrt{x + 3}', insertMode: 'replace' },
            { title: '\\text{inverse } f(x) = e^x', latex: '\\text{inverse } f(x) = e^x', insertMode: 'replace' },
            { title: '\\text{inverse } f(x) = \\ln(x)', latex: '\\text{inverse } f(x) = \\ln(x)', insertMode: 'replace' },
            { title: '\\text{inverse } \\sin(x)', latex: '\\text{inverse } \\sin(x)', insertMode: 'replace' },
            { title: '\\text{inverse } \\tan(x)', latex: '\\text{inverse } \\tan(x)', insertMode: 'replace' },
            { title: '\\text{inverse } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{inverse } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{inverse laplace } 1/(s(s+2))', latex: '\\text{inverse laplace } \\frac{1}{s(s+2)}', insertMode: 'replace' }
        ]
    },
    {
        id: 'tangent',
        label: 'Tangent',
        placeholderLatex: '\\text{tangent of } ',
        suggestions: [
            { title: '\\text{tangent of } f(x) = x^2, x = 1', latex: '\\text{tangent of } f(x) = x^2, x = 1', insertMode: 'replace' },
            { title: '\\text{tangent of } f(x) = x^3, x = 2', latex: '\\text{tangent of } f(x) = x^3, x = 2', insertMode: 'replace' },
            { title: '\\text{tangent of } \\sin(x), x = 0', latex: '\\text{tangent of } \\sin(x), x = 0', insertMode: 'replace' },
            { title: '\\text{tangent of } \\cos(x), x = 0', latex: '\\text{tangent of } \\cos(x), x = 0', insertMode: 'replace' },
            { title: '\\text{tangent of } e^x, x = 0', latex: '\\text{tangent of } e^x, x = 0', insertMode: 'replace' },
            { title: '\\text{tangent of } \\ln(x), x = 1', latex: '\\text{tangent of } \\ln(x), x = 1', insertMode: 'replace' },
            { title: '\\text{tangent of } 1/x, x = 1', latex: '\\text{tangent of } 1/x, x = 1', insertMode: 'replace' },
            { title: '\\text{tangent of } \\sqrt{x}, x = 4', latex: '\\text{tangent of } \\sqrt{x}, x = 4', insertMode: 'replace' },
            { title: '\\text{tangent of } f(x) = x^2 + 2x + 1, x = -1', latex: '\\text{tangent of } f(x) = x^2 + 2x + 1, x = -1', insertMode: 'replace' },
            { title: '\\text{tangent of } f(x) = (x^2 + 1)/(x - 1), x = 2', latex: '\\text{tangent of } f(x) = \\frac{x^2 + 1}{x - 1}, x = 2', insertMode: 'replace' }
        ]
    },
    {
        id: 'line',
        label: 'Line',
        placeholderLatex: '\\text{line } ',
        suggestions: [
            { title: '\\text{line } (0, 0), (2, 3)', latex: '\\text{line } (0, 0), (2, 3)', insertMode: 'replace' },
            { title: '\\text{line } (1, 2), (4, 2)', latex: '\\text{line } (1, 2), (4, 2)', insertMode: 'replace' },
            { title: '\\text{line } (2, 5), (2, -1)', latex: '\\text{line } (2, 5), (2, -1)', insertMode: 'replace' },
            { title: '\\text{line } (-1, 3), (2, -3)', latex: '\\text{line } (-1, 3), (2, -3)', insertMode: 'replace' },
            { title: '\\text{line } (3, -2), (6, 4)', latex: '\\text{line } (3, -2), (6, 4)', insertMode: 'replace' },
            { title: '\\text{line } (-2, -1), (4, 5)', latex: '\\text{line } (-2, -1), (4, 5)', insertMode: 'replace' },
            { title: '\\text{line } (-3, 0), (0, 6)', latex: '\\text{line } (-3, 0), (0, 6)', insertMode: 'replace' },
            { title: '\\text{line } (1, 1), (2, 4)', latex: '\\text{line } (1, 1), (2, 4)', insertMode: 'replace' },
            { title: '\\text{line } (2, 3), (5, 9)', latex: '\\text{line } (2, 3), (5, 9)', insertMode: 'replace' },
            { title: '\\text{line } (-4, 2), (1, -3)', latex: '\\text{line } (-4, 2), (1, -3)', insertMode: 'replace' }
        ]
    },
    {
        id: 'area',
        label: 'Area',
        placeholderLatex: '\\text{area } ',
        suggestions: [
            { title: '\\text{area } x^2 \\text{ from } 0 \\text{ to } 2', latex: '\\text{area } x^2 \\text{ from } 0 \\text{ to } 2', insertMode: 'replace' },
            { title: '\\text{area } \\sin(x) \\text{ from } 0 \\text{ to } \\pi', latex: '\\text{area } \\sin(x) \\text{ from } 0 \\text{ to } \\pi', insertMode: 'replace' },
            { title: '\\text{area } x \\text{ from } 0 \\text{ to } 5', latex: '\\text{area } x \\text{ from } 0 \\text{ to } 5', insertMode: 'replace' },
            { title: '\\text{area } (x^3 - x) \\text{ from } -1 \\text{ to } 1', latex: '\\text{area } (x^{3} - x) \\text{ from } -1 \\text{ to } 1', insertMode: 'replace' },
            { title: '\\text{area } e^x \\text{ from } 0 \\text{ to } 1', latex: '\\text{area } e^x \\text{ from } 0 \\text{ to } 1', insertMode: 'replace' },
            { title: '\\text{area } |x| \\text{ from } -2 \\text{ to } 2', latex: '\\text{area } |x| \\text{ from } -2 \\text{ to } 2', insertMode: 'replace' },
            { title: '\\text{area } (x^2 + 1) \\text{ from } -1 \\text{ to } 1', latex: '\\text{area } (x^{2} + 1) \\text{ from } -1 \\text{ to } 1', insertMode: 'replace' },
            { title: '\\text{area } (2x + 3) \\text{ from } 1 \\text{ to } 4', latex: '\\text{area } (2x + 3) \\text{ from } 1 \\text{ to } 4', insertMode: 'replace' },
            { title: '\\text{area } \\cos(x) \\text{ from } 0 \\text{ to } \\pi/2', latex: '\\text{area } \\cos(x) \\text{ from } 0 \\text{ to } \\pi/2', insertMode: 'replace' },
            { title: '\\text{area } (1/x) \\text{ from } 1 \\text{ to } 4', latex: '\\text{area } (1/x) \\text{ from } 1 \\text{ to } 4', insertMode: 'replace' }
        ]
    },
    {
        id: 'asymptotes',
        label: 'Asymptotes',
        placeholderLatex: '\\text{asymptotes } ',
        suggestions: [
            { title: '\\text{asymptotes } (x+1)/(x-2)', latex: '\\text{asymptotes } \\frac{x+1}{x-2}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (2x^2+3)/(x-1)', latex: '\\text{asymptotes } \\frac{2x^2+3}{x-1}', insertMode: 'replace' },
            { title: '\\text{asymptotes } 1/(x^2)', latex: '\\text{asymptotes } \\frac{1}{x^2}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (x^2+1)/(x)', latex: '\\text{asymptotes } \\frac{x^2+1}{x}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (x^2-4)/(x-2)', latex: '\\text{asymptotes } \\frac{x^2-4}{x-2}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (3x-1)/(x+5)', latex: '\\text{asymptotes } \\frac{3x-1}{x+5}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (x^2)/(x^2+1)', latex: '\\text{asymptotes } \\frac{x^2}{x^2+1}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (x^3)/(x^2+1)', latex: '\\text{asymptotes } \\frac{x^3}{x^2+1}', insertMode: 'replace' },
            { title: '\\text{asymptotes } 1/(x-3)^2', latex: '\\text{asymptotes } \\frac{1}{(x-3)^2}', insertMode: 'replace' },
            { title: '\\text{asymptotes } (x^2+2x+1)/(x^2-1)', latex: '\\text{asymptotes } \\frac{x^2+2x+1}{x^2-1}', insertMode: 'replace' }
        ]
    },
    {
        id: 'critical_points',
        label: 'Critical Points',
        placeholderLatex: '\\text{critical points } ',
        suggestions: [
            { title: '\\text{critical points } x^3 - 3x', latex: '\\text{critical points } x^3 - 3x', insertMode: 'replace' },
            { title: '\\text{critical points } x^4 - 4x^2', latex: '\\text{critical points } x^4 - 4x^2', insertMode: 'replace' },
            { title: '\\text{critical points } x^2 + 4x + 1', latex: '\\text{critical points } x^2 + 4x + 1', insertMode: 'replace' },
            { title: '\\text{critical points } \\sin(x)', latex: '\\text{critical points } \\sin(x)', insertMode: 'replace' },
            { title: '\\text{critical points } \\cos(x)', latex: '\\text{critical points } \\cos(x)', insertMode: 'replace' },
            { title: '\\text{critical points } e^x - x', latex: '\\text{critical points } e^x - x', insertMode: 'replace' },
            { title: '\\text{critical points } \\ln(x) - x', latex: '\\text{critical points } \\ln(x) - x', insertMode: 'replace' },
            { title: '\\text{critical points } x/(x^2+1)', latex: '\\text{critical points } \\frac{x}{x^2+1}', insertMode: 'replace' },
            { title: '\\text{critical points } \\sqrt{x} \\; (x \\ge 0)', latex: '\\text{critical points } \\sqrt{x} \\text{ on } x \\ge 0', insertMode: 'replace' },
            { title: '\\text{critical points } (x^2+1)/(x-1)', latex: '\\text{critical points } \\frac{x^2+1}{x-1}', insertMode: 'replace' }
        ]
    },
    {
        id: 'derivative',
        label: 'Derivative',
        placeholderLatex: '\\text{derivative } ',
        suggestions: [
            { title: '\\text{derivative } x^2', latex: '\\text{derivative } x^2', insertMode: 'replace' },
            { title: '\\text{derivative } x^3 - 5x + 1', latex: '\\text{derivative } x^3 - 5x + 1', insertMode: 'replace' },
            { title: '\\text{derivative } \\sqrt{x}', latex: '\\text{derivative } \\sqrt{x}', insertMode: 'replace' },
            { title: '\\text{derivative } 1/x', latex: '\\text{derivative } \\frac{1}{x}', insertMode: 'replace' },
            { title: '\\text{derivative } (x^2 + 1)/(x - 1)', latex: '\\text{derivative } \\frac{x^2 + 1}{x - 1}', insertMode: 'replace' },
            { title: '\\text{derivative } \\sin(x)', latex: '\\text{derivative } \\sin(x)', insertMode: 'replace' },
            { title: '\\text{derivative } \\cos(x)', latex: '\\text{derivative } \\cos(x)', insertMode: 'replace' },
            { title: '\\text{derivative } e^x', latex: '\\text{derivative } e^x', insertMode: 'replace' },
            { title: '\\text{derivative } \\ln(x)', latex: '\\text{derivative } \\ln(x)', insertMode: 'replace' },
            { title: '\\text{derivative } (x^2)\\sin(x)', latex: '\\text{derivative } (x^2)\\sin(x)', insertMode: 'replace' }
        ]
    },
    {
        id: 'domain',
        label: 'Domain',
        placeholderLatex: '\\text{domain } ',
        suggestions: [
            { title: '\\text{domain } \\sqrt{x-3}', latex: '\\text{domain } \\sqrt{x-3}', insertMode: 'replace' },
            { title: '\\text{domain } 1/(x-2)', latex: '\\text{domain } \\frac{1}{x-2}', insertMode: 'replace' },
            { title: '\\text{domain } \\ln(x)', latex: '\\text{domain } \\ln(x)', insertMode: 'replace' },
            { title: '\\text{domain } \\ln(x-1)', latex: '\\text{domain } \\ln(x-1)', insertMode: 'replace' },
            { title: '\\text{domain } 1/\\sqrt{x+2}', latex: '\\text{domain } \\frac{1}{\\sqrt{x+2}}', insertMode: 'replace' },
            { title: '\\text{domain } (x+1)/(x^2-9)', latex: '\\text{domain } \\frac{x+1}{x^2-9}', insertMode: 'replace' },
            { title: '\\text{domain } \\sqrt{x^2-4}', latex: '\\text{domain } \\sqrt{x^2-4}', insertMode: 'replace' },
            { title: '\\text{domain } 1/(x^2+1)', latex: '\\text{domain } \\frac{1}{x^2+1}', insertMode: 'replace' },
            { title: '\\text{domain } (x^2+3x+2)/(x+1)', latex: '\\text{domain } \\frac{x^2+3x+2}{x+1}', insertMode: 'replace' },
            { title: '\\text{domain } \\tan(x)', latex: '\\text{domain } \\tan(x)', insertMode: 'replace' }
        ]
    },
    {
        id: 'eigenvalues',
        label: 'Eigenvalues',
        placeholderLatex: '\\text{eigenvalues } ',
        suggestions: [
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvalues } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', latex: '\\text{eigenvalues } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', insertMode: 'replace' }
        ]
    },
    {
        id: 'eigenvectors',
        label: 'Eigenvectors',
        placeholderLatex: '\\text{eigenvectors } ',
        suggestions: [
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 2 & 0 \\\\ 0 & 5 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 3 & 1 \\\\ 0 & 3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 1 \\\\ 1 & 1 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 0 & 1 \\\\ -2 & -3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 4 & -1 \\\\ 2 & 1 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 1 & 0 & 0 \\\\ 0 & 2 & 0 \\\\ 0 & 0 & 3 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 0 & -1 \\\\ 1 & 0 \\end{pmatrix}', insertMode: 'replace' },
            { title: '\\text{eigenvectors } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', latex: '\\text{eigenvectors } \\begin{pmatrix} 5 & 2 & 0 \\\\ 2 & 5 & 0 \\\\ 0 & 0 & 1 \\end{pmatrix}', insertMode: 'replace' }
        ]
    },
    {
        id: 'expand',
        label: 'Expand',
        placeholderLatex: '\\text{expand } ',
        suggestions: [
            { title: '\\text{expand } (x+2)^2', latex: '\\text{expand } (x+2)^2', insertMode: 'replace' },
            { title: '\\text{expand } (x-3)(x+3)', latex: '\\text{expand } (x-3)(x+3)', insertMode: 'replace' },
            { title: '\\text{expand } (2x-1)(x+4)', latex: '\\text{expand } (2x-1)(x+4)', insertMode: 'replace' },
            { title: '\\text{expand } (x+1)^3', latex: '\\text{expand } (x+1)^3', insertMode: 'replace' },
            { title: '\\text{expand } (x-2)^3', latex: '\\text{expand } (x-2)^3', insertMode: 'replace' },
            { title: '\\text{expand } (x+2)(x^2-2x+4)', latex: '\\text{expand } (x+2)(x^2-2x+4)', insertMode: 'replace' },
            { title: '\\text{expand } (x+y)^2', latex: '\\text{expand } (x+y)^2', insertMode: 'replace' },
            { title: '\\text{expand } (a-b)^3', latex: '\\text{expand } (a-b)^3', insertMode: 'replace' },
            { title: '\\text{expand } (2x+3y)^2', latex: '\\text{expand } (2x+3y)^2', insertMode: 'replace' },
            { title: '\\text{expand } (x-1)(x^2+x+1)', latex: '\\text{expand } (x-1)(x^2+x+1)', insertMode: 'replace' }
        ]
    },
    {
        id: 'extreme_points',
        label: 'Extreme Points',
        placeholderLatex: '\\text{extreme points } ',
        suggestions: [
            { title: '\\text{extreme points } x^3 - 3x', latex: '\\text{extreme points } x^3 - 3x', insertMode: 'replace' },
            { title: '\\text{extreme points } x^4 - 4x^2', latex: '\\text{extreme points } x^4 - 4x^2', insertMode: 'replace' },
            { title: '\\text{extreme points } x^2 + 4x + 1', latex: '\\text{extreme points } x^2 + 4x + 1', insertMode: 'replace' },
            { title: '\\text{extreme points } \\sin(x) \\text{ on } [0, 2\\pi]', latex: '\\text{extreme points } \\sin(x) \\text{ on } [0, 2\\pi]', insertMode: 'replace' },
            { title: '\\text{extreme points } \\cos(x) \\text{ on } [0, 2\\pi]', latex: '\\text{extreme points } \\cos(x) \\text{ on } [0, 2\\pi]', insertMode: 'replace' },
            { title: '\\text{extreme points } e^x - x', latex: '\\text{extreme points } e^x - x', insertMode: 'replace' },
            { title: '\\text{extreme points } \\ln(x) - x', latex: '\\text{extreme points } \\ln(x) - x', insertMode: 'replace' },
            { title: '\\text{extreme points } x/(x^2+1)', latex: '\\text{extreme points } \\frac{x}{x^2+1}', insertMode: 'replace' },
            { title: '\\text{extreme points } -(x-2)^2 + 3', latex: '\\text{extreme points } -(x-2)^2 + 3', insertMode: 'replace' },
            { title: '\\text{extreme points } (x^2+1)/(x-1)', latex: '\\text{extreme points } \\frac{x^2+1}{x-1}', insertMode: 'replace' }
        ]
    }
];
