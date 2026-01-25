
import { estimateTokens } from '../tokenEstimator';
import { detectMultiQuestion } from '../multiQuestionDetector';

// ============================================================================
// 1. DATA GENERATORS
// ============================================================================

const ALGEBRA_TEMPLATES = [
    "Solve for x: 2x + 5 = 15",
    "x^2 + 5x + 6 = 0",
    "\\frac{1}{x} + \\frac{1}{y} = \\frac{1}{z}",
    "sqrt(x^2 + y^2) = r",
    "3x - 2y = 10",
    "Find the roots of x^2 - 4x + 4 = 0",
    "Simplify: (x+1)(x-1)",
    "Factorize: x^2 - 9",
    "Evaluate 5x^2 when x = 3",
    "y = mx + b"
];

const CALCULUS_TEMPLATES = [
    "Find the derivative of f(x) = x^3",
    "\\int_{0}^{\\infty} e^{-x} dx",
    "lim_{x \\to 0} \\frac{sin(x)}{x}",
    "dy/dx = 3y",
    "Find the area under the curve y=x^2 from 0 to 1",
    "\\sum_{n=1}^{\\infty} \\frac{1}{n^2}",
    "f'(x) = 2x + 1",
    "Integrate x cos(x) dx",
    "Determine the inflection points of f(x) = x^4 - 4x^3",
    "\\frac{d}{dx} (e^x \\sin x)"
];

const WORD_PROBLEMS = [
    "A train leaves New York traveling at 60 mph...",
    "If John has 5 apples and gives 2 to Mary...",
    "Calculate the probability of rolling two sixes.",
    "The area of a rectangle is 50 sq meters...",
    "A bacteria culture doubles every 3 hours.",
    "Find the volume of a sphere with radius 5.",
    "What is the kinetic energy of a 5kg mass moving at 10m/s?",
    "Three consecutive integers sum to 63.",
    "A ladder leans against a wall at a 45 degree angle.",
    "If a car accelerates from 0 to 60 in 5 seconds..."
];

const MULTI_PATTERNS = [
    (a: string, b: string) => `Q1: ${a} Q2: ${b}`,
    (a: string, b: string) => `1) ${a}\n2) ${b}`,
    (a: string, b: string) => `(a) ${a}\n(b) ${b}`,
    (a: string, b: string) => `${a}\n\n${b}`,
    (a: string, b: string) => `First, ${a}. Then, ${b}`,
    (a: string, b: string) => `${a} also ${b}`,
];

// ============================================================================
// 2. GENERATE 300+ QUESTIONS
// ============================================================================

function generateDataset() {
    const dataset: { id: number, text: string, type: string }[] = [];
    let id = 1;

    // A. Single Math (100 variants)
    for (let i = 0; i < 10; i++) {
        ALGEBRA_TEMPLATES.forEach(t => {
            dataset.push({ id: id++, text: `${t} (Variant ${i})`, type: 'Single Math' });
        });
    }

    // B. Math Heavy LaTeX (50 variants)
    for (let i = 0; i < 5; i++) {
        CALCULUS_TEMPLATES.forEach(t => {
            dataset.push({ id: id++, text: `${t} with parameter k=${i}`, type: 'Math Heavy' });
        });
    }

    // C. Word Problems (50 variants)
    for (let i = 0; i < 5; i++) {
        WORD_PROBLEMS.forEach(t => {
            dataset.push({ id: id++, text: `${t} [Case ${i}]`, type: 'Word Problem' });
        });
    }

    // D. Multi-Questions (100 variants)
    for (let i = 0; i < 100; i++) {
        const t1 = ALGEBRA_TEMPLATES[i % 10];
        const t2 = CALCULUS_TEMPLATES[i % 10];
        const pattern = MULTI_PATTERNS[i % MULTI_PATTERNS.length];
        dataset.push({ id: id++, text: pattern(t1, t2), type: 'Multi-Question' });
    }

    return dataset;
}

// ============================================================================
// 3. EXECUTE VALIDATION
// ============================================================================

async function runBatchValidation() {
    console.log("🚀 Starting Batch Validation (300+ Questions)...\n");

    const questions = generateDataset();
    console.log(`Initialized dataset with ${questions.length} unique items.\n`);

    const stats = {
        total: 0,
        mathHeavyDetected: 0,
        multiDetected: 0,
        multiHighConfidence: 0,
        autoSplitSuccess: 0
    };

    console.log("ID   | Type           | Tokens | Mode       | Multi? | Conf | Splits");
    console.log("-----|----------------|--------|------------|--------|------|-------");

    // Process mainly the first few, some middle, some last to show variety without spanning 300 lines fully if not needed,
    // but user asked to SEE 300. I will print them all in compacted format.

    for (const q of questions) {
        // Run Token Estimation
        const tokenRes = estimateTokens(q.text);

        // Run Multi-Question Detection
        const multiRes = detectMultiQuestion(q.text);

        // Update Stats
        stats.total++;
        if (tokenRes.mode === 'mathHeavy') stats.mathHeavyDetected++;
        if (multiRes.isMultiple) stats.multiDetected++;
        if (multiRes.confidence === 'high') stats.multiHighConfidence++;
        if (multiRes.suggestedSplits.length > 1) stats.autoSplitSuccess++;

        // Log row
        const idStr = q.id.toString().padEnd(4);
        const typeStr = q.type.padEnd(14).slice(0, 14);
        const tokenStr = tokenRes.tokens.toString().padEnd(6);
        const modeStr = tokenRes.mode.padEnd(10);
        const multiStr = (multiRes.isMultiple ? "YES" : "NO").padEnd(6);
        const confStr = multiRes.isMultiple ? multiRes.confidence.padEnd(4) : "-   ";
        const splitStr = multiRes.suggestedSplits.length.toString();

        console.log(`${idStr} | ${typeStr} | ${tokenStr} | ${modeStr} | ${multiStr} | ${confStr} | ${splitStr}`);
    }

    // ============================================================================
    // 4. SUMMARY REPORT
    // ============================================================================
    console.log("\n==================================================");
    console.log("✅ VALIDATION SUMMARY");
    console.log("==================================================");
    console.log(`Total Questions Processed: ${stats.total}`);
    console.log(`Math-Heavy Inputs:         ${stats.mathHeavyDetected} (${((stats.mathHeavyDetected / stats.total) * 100).toFixed(1)}%)`);
    console.log(`Multi-Questions Detected:  ${stats.multiDetected} (${((stats.multiDetected / stats.total) * 100).toFixed(1)}%)`);
    console.log(`  - High Confidence:       ${stats.multiHighConfidence}`);
    console.log(`Auto-Split Successful:     ${stats.autoSplitSuccess} (${((stats.autoSplitSuccess / stats.multiDetected) * 100).toFixed(1)}% of detected)`);
    console.log("==================================================");
}

runBatchValidation();
