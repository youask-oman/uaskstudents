import { normalizeAndFixColors, escapeAllDollars, sanitizeLatex } from '../MathUtils';

describe('MathRenderer Preprocessing Logic', () => {

    describe('escapeAllDollars', () => {
        test('escapes ALL dollars in prose', () => {
            // "Cost is $5" -> "Cost is \$5"
            expect(escapeAllDollars('Cost is $5')).toBe('Cost is \\$5');
        });

        test('escapes dollars even in math-like strings (Strict Mode enforcement)', () => {
            // "$x^2$" -> "\$x^2\$" (Strict mode ignores $ as delimiter)
            expect(escapeAllDollars('$x^2$')).toBe('\\$x^2\\$');
        });

        test('does NOT escape dollars inside code blocks', () => {
            const input = 'Code: ```\n$var = 5\n```';
            expect(escapeAllDollars(input)).toBe(input);
        });

        test('escapes dollars mixed with code', () => {
            const input = 'Price $5. Code: `echo $PATH`. End.';
            const expected = 'Price \\$5. Code: `echo $PATH`. End.';
            expect(escapeAllDollars(input)).toBe(expected);
        });
    });

    describe('normalizeAndFixColors (The "OnTheRight" Fix)', () => {
        test('normalizes \\blue{text} to \\textcolor{blue}', () => {
            expect(normalizeAndFixColors('\\blue{x}')).toBe('\\textcolor{blue}{x}');
        });

        test('wraps prose in \\text{} preserving spaces', () => {
            // \\blue{on the right} -> \\textcolor{blue}{\\text{on the right}}
            expect(normalizeAndFixColors('\\blue{on the right}')).toBe('\\textcolor{blue}{\\text{on the right}}');
        });
    });

    describe('Integration Safety', () => {
        test('Sanitize removes dangerous artifacts', () => {
            const input = "some text .textLine : artifact";
            expect(sanitizeLatex(input)).toContain('\\text{Line: }');
        });
    });

});
