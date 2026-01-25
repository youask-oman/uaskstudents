import { validateMathQuery } from "../src/lib/mathValidation";
import { MODES } from "../src/lib/modes";
import { INPUT_MODES } from "../src/lib/inputModes";

const modeTemplates = MODES.flatMap((mode) => mode.suggestions.map((s) => s.latex));
const inputTemplates = INPUT_MODES.flatMap((mode) => mode.templates);
const allTemplates = [...modeTemplates, ...inputTemplates];

const failures = allTemplates
    .map((template) => ({ template, error: validateMathQuery(template) }))
    .filter((entry) => entry.error);

console.log(`Templates checked: ${allTemplates.length}`);
console.log(`Failures: ${failures.length}`);

if (failures.length > 0) {
    failures.slice(0, 50).forEach((entry, index) => {
        console.log(`${index + 1}. ${entry.error} -> ${entry.template}`);
    });
    process.exit(1);
}
