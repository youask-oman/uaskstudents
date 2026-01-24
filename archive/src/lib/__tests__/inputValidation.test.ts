/**
 * Unit Tests for Token Estimator and Multi-Question Detector
 */

import { estimateTokens, isInputTooLong, getTokenStatus } from '../tokenEstimator';
import { detectMultiQuestion, autoSplitQuestions, shouldShowSplitUI } from '../multiQuestionDetector';
import { describe, it, expect } from './test-utils';

// ============================================================================
// TOKEN ESTIMATOR TESTS
// ============================================================================

describe('estimateTokens', () => {
    describe('normal text estimation', () => {
        it('should estimate ~500 tokens for 2000 chars of normal text', () => {
            const normalText = 'The quick brown fox jumps over the lazy dog. '.repeat(41);
            // This is > 1800 chars
            expect(normalText.length).toBeGreaterThan(1800);
            expect(normalText.length).toBeLessThan(2200);

            const result = estimateTokens(normalText);
            expect(result.mode).toBe('normal');
            expect(result.tokens).toBeGreaterThan(400);
            expect(result.tokens).toBeLessThan(600);
        });

        it('should return 0 tokens for empty input', () => {
            const result = estimateTokens('');
            expect(result.tokens).toBe(0);
            expect(result.chars).toBe(0);
            expect(result.mode).toBe('normal');
        });
    });

    describe('math-heavy detection', () => {
        it('should detect math-heavy content with LaTeX', () => {
            const mathText = `
                \\frac{x^2 + y^2}{z} = \\sqrt{16}
                \\begin{equation}
                x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
                \\end{equation}
            `;
            const result = estimateTokens(mathText);
            expect(result.mode).toBe('mathHeavy');
            expect(result.signals.latexCommands).toBeGreaterThan(0);
        });

        it('should detect math-heavy content with many operators', () => {
            const mathText = 'x = 5, y = 10, z = x + y - 3 * 2 / 4 + (a - b)';
            const result = estimateTokens(mathText);
            expect(result.signals.operators).toBeGreaterThan(5);
        });

        it('should apply penalty for math-heavy content', () => {
            const normalText = 'a'.repeat(100);
            const mathText = '\\frac{1}{2} + \\sqrt{4} = 2.5, x = 123456789'.repeat(5);

            const normalResult = estimateTokens(normalText);
            const mathResult = estimateTokens(mathText);

            // Math-heavy should produce more tokens per character
            if (mathResult.mode === 'mathHeavy') {
                // chars/tokens ratio should be lower for math
                const normalRatio = normalResult.chars / normalResult.tokens;
                const mathRatio = mathResult.chars / mathResult.tokens;
                expect(mathRatio).toBeLessThan(normalRatio);
            }
        });
    });
});

describe('isInputTooLong', () => {
    it('should return true when tokens exceed limit', () => {
        const longText = 'test '.repeat(1000); // ~5000 chars
        expect(isInputTooLong(longText, 1000)).toBe(true);
    });

    it('should return false for short input', () => {
        expect(isInputTooLong('x = 5', 1000)).toBe(false);
    });
});

describe('getTokenStatus', () => {
    it('should return error status when over limit', () => {
        const estimate = { tokens: 1200, mode: 'normal' as const, chars: 4800, signals: { latexCommands: 0, operators: 0, digits: 0, parentheses: 0, equationLines: 0 } };
        const status = getTokenStatus(estimate, 1000);
        expect(status.status).toBe('error');
        expect(status.message).toContain('too long');
    });

    it('should return warning status when near limit', () => {
        const estimate = { tokens: 850, mode: 'normal' as const, chars: 3400, signals: { latexCommands: 0, operators: 0, digits: 0, parentheses: 0, equationLines: 0 } };
        const status = getTokenStatus(estimate, 1000);
        expect(status.status).toBe('warning');
    });

    it('should return ok status for normal input', () => {
        const estimate = { tokens: 200, mode: 'normal' as const, chars: 800, signals: { latexCommands: 0, operators: 0, digits: 0, parentheses: 0, equationLines: 0 } };
        const status = getTokenStatus(estimate, 1000);
        expect(status.status).toBe('ok');
    });
});

// ============================================================================
// MULTI-QUESTION DETECTOR TESTS
// ============================================================================

describe('detectMultiQuestion', () => {
    describe('question mark detection', () => {
        it('should detect multiple question marks', () => {
            const text = 'What is x? And what is y?';
            const result = detectMultiQuestion(text);
            expect(result.questionMarks).toBe(2);
            expect(result.isMultiple).toBe(true);
        });

        it('should not flag single question', () => {
            const text = 'What is x + y?';
            const result = detectMultiQuestion(text);
            expect(result.questionMarks).toBe(1);
        });
    });

    describe('numbered pattern detection', () => {
        it('should detect Q1, Q2 patterns', () => {
            const text = 'Q1: Solve x = 5. Q2: Find y if y = x + 3';
            const result = detectMultiQuestion(text);
            expect(result.isMultiple).toBe(true);
            expect(result.matchedPatterns.some(p => p.includes('Q'))).toBe(true);
        });

        it('should detect 1), 2) patterns', () => {
            const text = '1) x = 5\n2) y = 10';
            const result = detectMultiQuestion(text);
            expect(result.isMultiple).toBe(true);
        });

        it('should detect (a), (b) patterns', () => {
            const text = '(a) Find x\n(b) Find y';
            const result = detectMultiQuestion(text);
            expect(result.isMultiple).toBe(true);
        });
    });

    describe('single equation input', () => {
        it('should not flag single equation', () => {
            const text = 'x^2 + 5x + 6 = 0';
            const result = detectMultiQuestion(text);
            expect(result.isMultiple).toBe(false);
        });

        it('should not flag single word problem', () => {
            const text = 'If a train travels at 60 mph for 2 hours, how far does it go?';
            const result = detectMultiQuestion(text);
            expect(result.isMultiple).toBe(false);
        });
    });
});

describe('autoSplitQuestions', () => {
    it('should split numbered questions', () => {
        const text = 'Q1: x = 5. Q2: y = 10';
        const splits = autoSplitQuestions(text);
        expect(splits.length).toBeGreaterThanOrEqual(1);
    });

    it('should split by blank lines', () => {
        const text = 'Evaluate x = 5\n\nEvaluate y = 10';
        const splits = autoSplitQuestions(text);
        expect(splits.length).toBe(2);
    });
});

describe('shouldShowSplitUI', () => {
    it('should return true for multiple questions', () => {
        expect(shouldShowSplitUI('Q1: x=1 Q2: y=2')).toBe(true);
    });

    it('should return false for single question', () => {
        expect(shouldShowSplitUI('x = 5')).toBe(false);
    });
});
