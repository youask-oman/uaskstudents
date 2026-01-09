export type ModeId = 'simplify' | 'solve_for' | 'inverse' | 'tangent' | 'area';

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
            { title: '\\sqrt{50}', latex: '\\sqrt{#?}' },
            { title: '\\ln(e)', latex: '\\ln(#?)' },
            { title: '\\frac{2}{4}', latex: '\\frac{#?}{#?}' },
            { title: '(a+b)^2', latex: '(#?+#?)^2' },
            { title: '\\sin^2 + \\cos^2', latex: '\\sin^2(#?) + \\cos^2(#?)' }
        ]
    },
    {
        id: 'solve_for',
        label: 'Solve For',
        placeholderLatex: '\\text{solve for } x, ',
        suggestions: [
            { title: '\\text{solve for } x', latex: '\\text{solve for } x, #? = #?', insertMode: 'replace' },
            { title: '\\text{solve for } t', latex: '\\text{solve for } t, #? = #?', insertMode: 'replace' },
            { title: 'Quad. Eq.', latex: '\\text{solve for } x, ax^2+bx+c=0', insertMode: 'replace' },
            { title: 'System', latex: '\\begin{cases} x+y=1 \\\\ x-y=0 \\end{cases}', insertMode: 'append' }
        ]
    },
    {
        id: 'inverse',
        label: 'Inverse',
        placeholderLatex: '\\text{inverse of } ',
        suggestions: [
            { title: 'f(x) = ...', latex: '\\text{inverse of } f(x) = #?', insertMode: 'replace' },
            { title: 'Matrix', latex: '\\text{inverse of } \\begin{pmatrix} #? & #? \\\\ #? & #? \\end{pmatrix}' }
        ]
    },
    {
        id: 'tangent',
        label: 'Tangent',
        placeholderLatex: '\\text{tangent of } ',
        suggestions: [
            { title: 'at x = a', latex: '\\text{tangent of } f(x)=#? \\text{ at } x=#?', insertMode: 'replace' }
        ]
    },
    {
        id: 'area',
        label: 'Area',
        placeholderLatex: '\\text{area under } ',
        suggestions: [
            { title: 'Integral', latex: '\\int_{#?}^{#?} #? \\, dx', insertMode: 'append' },
            { title: 'Between Curves', latex: '\\text{area between } f(x)=#? \\text{ and } g(x)=#?', insertMode: 'replace' }
        ]
    }
];
