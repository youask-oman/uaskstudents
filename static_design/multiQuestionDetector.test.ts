// multiQuestionDetector.test.ts
import { describe, it, expect } from "vitest";
import { detectMultiIntent, autoSplitInput } from "./multiQuestionDetector";

describe("multi intent detector", () => {
  it("detects assignment style: anchor + bullet list (no declared count)", () => {
    const text = `
Problem: Forced Heat Equation + Spectral Expansion + Error Control
Let u(x,t) solve ...
You must do ALL of the following:
- State the PDE, boundary conditions...
- Derive the eigenvalue problem...
- Normalize the eigenfunctions...
- Expand u(x,t) ...
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.taskCount).toBeGreaterThanOrEqual(4);
    expect(r.tasksExtracted.length).toBeGreaterThanOrEqual(4);
    expect(r.allowSingleBypass).toBe(false);
  });

  it("detects assignment style: declared count + numbered items", () => {
    const text = `
Problem: Quadratic + Optimization + Constraints
You must do ALL of the following (12 requirements):
1) Write the fencing constraint equation relating x and y.
2) Write the area function A in terms of x and y.
3) Substitute the constraint to express A as a function of a single variable.
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.signals.declaredTaskCount).toBe(12);
    expect(r.taskCount).toBe(12); // declared overrides
    expect(r.reasons.join(" ")).toMatch(/Declared 12/);
  });

  it("detects multi-problem: Problem headers >= 2", () => {
    const text = `
Problem: One
Do this.

Problem: Two
Do that.
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("multi_problem");
    expect(r.shouldBlockStandardSolve).toBe(true);
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBe(2);
  });

  it("detects multi-question: question marks + connectors", () => {
    const text = `Solve x^2=4? Then compute x+1?`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("multi_question");
  });

  it("assignment autosplit preserves context", () => {
    const text = `
Problem: Test
Given f(x)=x^2.
You must do all of the following:
- Find f(2).
- Find f(3).
`;
    const r = detectMultiIntent(text);
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBe(2);
    expect(splits[0]).toMatch(/Problem: Test/);
    expect(splits[0]).toMatch(/Task:/);
  });
});
