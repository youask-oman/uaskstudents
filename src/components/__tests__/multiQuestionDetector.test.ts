import { autoSplitInput, detectMultiIntent } from "@/lib/multiQuestionDetector";
import { MAX_TASKS_ALLOW_SINGLE_BYPASS } from "@/lib/tokenBudget";

describe("multi intent detector", () => {
  const assignmentAnchorFixture = `
Problem: Forced Heat Equation + Spectral Expansion + Error Control
Let u(x,t) solve ...
You must do ALL of the following:
- State the PDE, boundary conditions...
- Derive the eigenvalue problem...
- Normalize the eigenfunctions...
- Expand u(x,t) ...
`;

  const declaredCountFixture = `
Problem: Quadratic + Optimization + Constraints
You must do ALL of the following (12 requirements):
1) Write the fencing constraint equation relating x and y.
2) Write the area function A in terms of x and y.
3) Substitute the constraint to express A as a function of a single variable.
`;

  it("requirements anchor + bullet list (no declared count) => single_problem_multi_task", () => {
    const r = detectMultiIntent(assignmentAnchorFixture);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.taskCount).toBeGreaterThanOrEqual(4);
    expect(r.tasksExtracted.length).toBeGreaterThanOrEqual(4);
  });

  it("declared count + numbered list => single_problem_multi_task with taskCount=12", () => {
    const r = detectMultiIntent(declaredCountFixture);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.signals.declaredTaskCount).toBe(12);
    expect(r.taskCount).toBe(12);
  });

  it("two problem headers => multi_problem and autosplit 2", () => {
    const text = `
Problem: One
Do this.

Problem: Two
Do that.
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("multi_problem");
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBe(2);
  });

  it("two question marks => multi_question", () => {
    const text = "Solve x^2=4? Then compute x+1?";
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("multi_question");
  });

  it("bypass exploit closure disables bypass when taskCount is above MAX_TASKS_ALLOW_SINGLE_BYPASS", () => {
    const tasks = Array.from({ length: MAX_TASKS_ALLOW_SINGLE_BYPASS + 1 }, (_, idx) => `- Task ${idx + 1}`).join("\n");
    const text = `
Problem: Long assignment
You must do all of the following:
${tasks}
`;
    const r = detectMultiIntent(text);
    expect(r.taskCount).toBeGreaterThan(MAX_TASKS_ALLOW_SINGLE_BYPASS);
    expect(r.allowSingleBypass).toBe(false);
  });

  it("assignment autosplit preserves context on every split", () => {
    const text = `
Problem: Test
Given f(x)=x^2.
You must do all of the following:
- Find f(2).
- Find f(3).
- Find f(4).
- Find f(5).
`;
    const r = detectMultiIntent(text);
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBe(4);
    for (const split of splits) {
      expect(split).toMatch(/Problem: Test/);
      expect(split).toMatch(/Given f\(x\)=x\^2\./);
      expect(split).toMatch(/Task:/);
    }
  });

  it("false positive control: single question with one bullet does not trigger assignment mode", () => {
    const text = `
Find the derivative of x^2.
- Show the final answer only.
`;
    const r = detectMultiIntent(text);
    expect(r.classification).not.toBe("single_problem_multi_task");
  });

  it("unnumbered requirements lines are split by imperative starts (12 tasks)", () => {
    const text = `
A rectangular garden is to be built against a straight wall, so only THREE sides need fencing.
You have 48 meters of fencing available. Let the two equal sides perpendicular to the wall be x meters each,
and the side parallel to the wall be y meters.

You must do ALL of the following

Write the fencing constraint equation relating x and y.
Write the area function A in terms of x and y.
Substitute the constraint to express A as a function of a single variable (A(x) only).
State the domain (allowed values) of x based on the physical constraints.
Expand and simplify A(x) into standard quadratic form.
Identify whether A(x) opens upward or downward and explain what that implies about maximum/minimum.
Find the x-value that maximizes area by using the vertex formula x = -b/(2a) (no calculus).
Find the corresponding y-value using the constraint.
Compute the maximum area exactly (and also as a decimal to 2 decimal places).
Verify your result by completing the square for A(x) and showing the maximum directly.
Determine for which x-values the area is at least 180 m^2 (solve the inequality A(x) ≥ 180).
Interpret the inequality solution set in words (what side lengths are acceptable and why).
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.taskCount).toBe(12);
    expect(r.tasksExtracted.length).toBe(12);
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBe(12);
    expect(splits[0]).toMatch(/Task:\nWrite the fencing constraint equation/);
  });

  it("implicit imperative block (no anchor) is classified as single_problem_multi_task", () => {
    const text = `
Let n be a positive integer and let ζ = e^{2πi/n}. Consider the polynomial
P(z) = z^n - 1.

List all roots of P(z) in complex exponential form and in terms of ζ.
Show that the roots lie on the unit circle and are equally spaced in angle.
Prove that Σ_{k=0}^{n-1} ζ^k = 0.
Prove that ∏_{k=1}^{n-1} (1 - ζ^k) = n.
Use the factorization z^n - 1 = ∏_{k=0}^{n-1} (z - ζ^k) to justify your product identity.
Explain briefly why the result is real and positive despite complex factors.
State any assumptions about n and confirm the identity for n=3 and n=4 by direct computation.
`;
    const r = detectMultiIntent(text);
    expect(r.classification).toBe("single_problem_multi_task");
    expect(r.taskCount).toBeGreaterThanOrEqual(4);
    const splits = autoSplitInput(text, r);
    expect(splits.length).toBeGreaterThanOrEqual(4);
    expect(splits[0]).toMatch(/Task:\n/);
  });
});
