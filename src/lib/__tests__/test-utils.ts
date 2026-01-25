export function describe(name: string, fn: () => void) {
    console.log(`\n🧩 ${name}`);
    fn();
}

export function it(name: string, fn: () => void) {
    try {
        fn();
        console.log(`  ✓ ${name}`);
    } catch (error) {
        console.error(`  ✗ ${name}`);
        if (error instanceof Error) {
            console.error(`     ${error.message}`);
        } else {
            console.error(`     ${String(error)}`);
        }
    }
}

export function expect<T>(actual: T) {
    return {
        toBe(expected: T) {
            if (actual !== expected) {
                throw new Error(`Expected ${expected} but got ${actual}`);
            }
        },
        toBeGreaterThan(expected: number) {
            if (typeof actual !== "number") {
                throw new Error(`Expected a number but got ${typeof actual}`);
            }
            if (actual <= expected) {
                throw new Error(`Expected ${actual} to be greater than ${expected}`);
            }
        },
        toBeLessThan(expected: number) {
            if (typeof actual !== "number") {
                throw new Error(`Expected a number but got ${typeof actual}`);
            }
            if (actual >= expected) {
                throw new Error(`Expected ${actual} to be less than ${expected}`);
            }
        },
        toBeGreaterThanOrEqual(expected: number) {
            if (typeof actual !== "number") {
                throw new Error(`Expected a number but got ${typeof actual}`);
            }
            if (actual < expected) {
                throw new Error(`Expected ${actual} to be greater than or equal to ${expected}`);
            }
        },
        toContain(expected: string) {
            if (typeof actual !== "string") {
                throw new Error(`Expected a string but got ${typeof actual}`);
            }
            if (!actual.includes(expected)) {
                throw new Error(`Expected string to contain "${expected}"`);
            }
        }
    };
}
