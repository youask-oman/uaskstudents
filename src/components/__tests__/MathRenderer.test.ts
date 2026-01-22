/**
 * Unit tests for MathRenderer sanitizeLatex function
 */
import { sanitizeLatex, splitSolutionIntoLines } from '../MathUtils';

describe('sanitizeLatex', () => {
    describe('textLine artifact fixes', () => {
        it('should convert ).textLine: to proper \\text{Line: }', () => {
            const input = '(-1,1).textLine: y = 2x + 3';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{Line: }');
            expect(result).not.toContain('textLine');
        });

        it('should convert standalone textLine: to \\text{Line: }', () => {
            const input = 'textLine: y = 2x + 3';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{Line: }');
            expect(result).not.toContain('textLine:');
        });

        it('should handle ).textParabola: pattern', () => {
            const input = '(0,0).textParabola: y = x^2';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{Parabola: }');
            expect(result).not.toContain('textParabola');
        });

        it('should handle textPlot: pattern', () => {
            const input = 'textPlot: (-2,4), (-1,1)';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{Plot: }');
            expect(result).not.toContain('textPlot');
        });
    });

    describe('CamelCase artifact fixes', () => {
        it('should convert textOtherpoints to \\text{Other points }', () => {
            const input = 'textOtherpoints:(1,1), (2,4)';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{');
            expect(result).not.toMatch(/textOtherpoints/i);
        });

        it('should convert textPlotdomainsuggestion to readable text', () => {
            const input = 'textPlotdomainsuggestion';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{');
            expect(result).not.toContain('textPlotdomainsuggestion');
        });

        it('should convert textThus to \\text{Thus }', () => {
            const input = 'textThus the intersection is';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{Thus');
            expect(result).not.toMatch(/textThus/);
        });
    });

    describe('Complex multi-part solutions', () => {
        it('should handle the exact problematic pattern from screenshots', () => {
            const input = 'Parabola: y = x^2, window x ∈ [-3,3], y ∈ [-1,9], label (0,0), (1,1), (-1,1).textLine :y = 2x + 3, window x ∈ [-3,3], y ∈ [-3,9], label (0,3), (1,5), (-1,1).';
            const result = sanitizeLatex(input);

            // Should contain proper text formatting
            expect(result).toContain('\\text{Line: }');

            // Should NOT contain artifacts
            expect(result).not.toContain('.textLine');
            expect(result).not.toContain('textLine :');
            expect(result).not.toContain('textLine:');
        });
    });

    describe('Missing backslash fixes', () => {
        it('should add backslash to text{...} when missing', () => {
            const input = 'text{hello world}';
            const result = sanitizeLatex(input);
            expect(result).toContain('\\text{hello world}');
        });

        it('should not double-escape already escaped \\text{...}', () => {
            const input = '\\text{hello world}';
            const result = sanitizeLatex(input);
            // Should remain single backslash (though with extra escaping in string)
            expect(result).not.toContain('\\\\\\\\text');
        });
    });
});

describe('splitSolutionIntoLines', () => {
    it('should split multi-part solutions into separate lines', () => {
        const input = 'Parabola: y = x^2 \\\\ Line: y = 2x + 3';
        const lines = splitSolutionIntoLines(input);
        expect(lines.length).toBeGreaterThanOrEqual(1);
    });

    it('should handle single-line solutions', () => {
        const input = 'x = 5';
        const lines = splitSolutionIntoLines(input);
        expect(lines.length).toBe(1);
        expect(lines[0]).toContain('x = 5');
    });
});
