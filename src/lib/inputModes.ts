/**
 * Input Mode Selector Configuration
 * 
 * Defines the different input modes for the solve page:
 * - Expression: Direct math expressions
 * - Word Problem: Natural language math problems
 * - Graphing: Equations to plot
 */

export type InputModeId = 'expression' | 'word_problem' | 'graphing';

export interface InputMode {
    id: InputModeId;
    label: string;
    icon: string;
    placeholder: string;
    description: string;
    templates: string[];
}

export const INPUT_MODES: InputMode[] = [
    {
        id: 'expression',
        label: 'Expression',
        icon: 'calculate',
        placeholder: 'Enter a math expression, e.g., x^2 + 5x + 6 = 0',
        description: 'Solve equations, simplify expressions, or evaluate formulas',
        templates: [
            'x^2 - 4 = 0',
            '\\frac{d}{dx}(x^3)',
            '\\int_0^1 x^2 dx',
            '\\lim_{x \\to 0} \\frac{\\sin x}{x}',
        ],
    },
    {
        id: 'word_problem',
        label: 'Word Problem',
        icon: 'description',
        placeholder: 'Describe your math problem in words...',
        description: 'Translate word problems into equations and solve step-by-step',
        templates: [
            'A train travels at 60 mph. How long to go 180 miles?',
            'Find two numbers that add to 10 and multiply to 24',
            'A rectangle has perimeter 20. Find dimensions if length is 3 more than width.',
        ],
    },
    {
        id: 'graphing',
        label: 'Graphing',
        icon: 'show_chart',
        placeholder: 'Enter equation(s) to graph, e.g., y = x^2',
        description: 'Plot functions, find intersections, analyze graphs',
        templates: [
            'y = x^2',
            'y = sin(x)',
            'y = x^2 and y = 2x + 3',
            'x^2 + y^2 = 25',
        ],
    },
];

/**
 * Graphing-specific options
 */
export interface GraphingOptions {
    /** Whether to plot multiple equations on separate axes */
    separatePlots: boolean;
    /** Optional x-axis domain */
    xMin?: number;
    xMax?: number;
    /** Optional y-axis domain */
    yMin?: number;
    yMax?: number;
}

export const DEFAULT_GRAPHING_OPTIONS: GraphingOptions = {
    separatePlots: false,
    xMin: undefined,
    xMax: undefined,
    yMin: undefined,
    yMax: undefined,
};
