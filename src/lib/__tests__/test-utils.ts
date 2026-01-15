
export function describe(name: string, fn: () => void) {
    console.log(`\n📦 ${name}`);
    fn();
}

export function it(name: string, fn: () => void) {
    try {
        fn();
        console.log(`  ✅ ${name}`);
    } catch (e: any) {
        console.error(`  ❌ ${name}`);
        console.error(`     ${e.message}`);
    }
}

export function expect(actual: any) {
    return {
        toBe: (expected: any) => {
            if (actual !== expected) {
                throw new Error(`Expected ${expected} but got ${actual}`);
            }
        },
        toBeGreaterThan: (expected: number) => {
            if (actual <= expected) {
                throw new Error(`Expected ${actual} to be greater than ${expected}`);
            }
        },
        toBeLessThan: (expected: number) => {
            if (actual >= expected) {
                throw new Error(`Expected ${actual} to be less than ${expected}`);
            }
        },
        toBeGreaterThanOrEqual: (expected: number) => {
            if (actual < expected) {
                throw new Error(`Expected ${actual} to be greater than or equal to ${expected}`);
            }
        },
        toContain: (expected: string) => {
            if (typeof actual === 'string' && !actual.includes(expected)) {
                throw new Error(`Expected string to contain "${expected}"`);
            }
        }
    };
}
