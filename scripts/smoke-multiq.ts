import { autoSplitQuestions, detectMultiQuestion } from "../src/lib/multiQuestionDetector";

const fixtures: Array<{ name: string; text: string; expected: number }> = [
    {
        name: "Complex Analysis: Singularities, Residues, and Mapping",
        expected: 10,
        text: `Complex Analysis: Singularities, Residues, and Mapping
Let f(z) = (z^2 + 1) / ( z (z - 1)^2 (z + 2) ).

1. Classify all singularities of f and state their orders.
2. Compute the residues at each singularity.
3. Compute ∮_{|z|=3} f(z) dz.
4. Find the partial fraction decomposition of f(z).
5. Compute ∫_{0}^{2π} f(3e^{it}) · 3i e^{it} dt and relate it to (3).
6. Determine the Laurent series of f about z=1 valid in 0 < |z-1| < 1.
7. Determine the Laurent series of f about z=0 valid in 0 < |z| < 1.
8. Evaluate ∫_{-∞}^{∞} 1 / (x^4 + 1) dx using residues (outline poles and contour).
9. Find a conformal map that sends the upper half-plane to the unit disk and apply it to z=i and z=2i.
10. Determine whether f has an antiderivative on C \\ {0,1,-2}. Justify using residues or winding.`,
    },
    {
        name: "Real Analysis / Measure Theory: Convergence and Integration",
        expected: 10,
        text: `Real Analysis / Measure Theory: Convergence and Integration
Let (f_n) be defined on [0,1] by f_n(x) = n x (1 - x)^n.

1. Show f_n ≥ 0 and compute ∫_0^1 f_n(x) dx.
2. Determine pointwise limit of f_n(x) as n → ∞ for x in [0,1].
3. Determine whether f_n → 0 uniformly on [0,1].
4. Compute lim_{n→∞} ∫_0^1 f_n(x) dx and compare with ∫_0^1 lim_{n→∞} f_n(x) dx.
5. State which theorem (DCT/MCT/Fatou) applies and why.
6. Find where f_n attains its maximum and compute max_x f_n(x).
7. Prove (f_n) is tight in the sense of mass concentrating near 0 (formalize).
8. Define g_n(x)=f_n(x)/∫_0^1 f_n and interpret g_n as a density; identify weak limit as a measure.
9. Decide whether (f_n) is Cauchy in L^1([0,1]) and justify.
10. Modify f_n to make it converge to a nonzero function in L^1 and explain the construction.`,
    },
    {
        name: "Linear Algebra / Spectral Theory: Diagonalization and Quadratic Forms",
        expected: 10,
        text: `Linear Algebra / Spectral Theory: Diagonalization and Quadratic Forms
Let A = [[4,1,1],[1,4,1],[1,1,4]].

1. Compute eigenvalues of A.
2. Find an orthonormal eigenbasis of R^3.
3. Diagonalize A as A = QΛQ^T.
4. Compute A^n explicitly (closed form).
5. Compute exp(tA) explicitly using the spectral decomposition.
6. Determine whether A is positive definite and justify via eigenvalues or principal minors.
7. Compute the condition number κ2(A).
8. Solve Ax=b for b=(1,2,3)^T using the eigen-decomposition method (not Gaussian elimination).
9. Compute the Rayleigh quotient R(x)=x^T A x / (x^T x) and find its min and max values.
10. Consider B = A - αI. Find all α such that B is positive semidefinite.`,
    },
    {
        name: "Multivariable Calculus: Change of Variables and Jacobians",
        expected: 10,
        text: `Multivariable Calculus: Change of Variables and Jacobians
Let D be the region in R^2 bounded by x>0, y>0, and x y ≤ 1, and x ≤ 2.

1. Sketch D clearly.
2. Set up ∬_D 1 dA using iterated integrals in both orders.
3. Compute Area(D).
4. Evaluate ∬_D (x + y) dA.
5. Use the substitution u = x y, v = x to transform D; compute Jacobian |∂(x,y)/∂(u,v)|.
6. Rewrite the integral from (4) in (u,v) coordinates and compute it.
7. Evaluate ∬_D ln(xy) dA.
8. Determine whether ∬_D 1/(xy) dA converges; if it does, compute it; if not, explain divergence.
9. Compute E[X] and E[Y] if (X,Y) is uniform on D (as a probability region).
10. Compute Cov(X,Y) under the uniform distribution on D.`,
    },
    {
        name: "Ordinary Differential Equations: Sturm-Liouville and Series",
        expected: 10,
        text: `Ordinary Differential Equations: Sturm-Liouville and Series
Consider y'' + λ y = 0 on (0,π) with boundary conditions y(0)=0 and y'(π)=0.

1. Find all eigenvalues λ and corresponding eigenfunctions.
2. Normalize the eigenfunctions in L^2(0,π).
3. Show the eigenfunctions form an orthogonal set.
4. Expand f(x)=x as a series in these eigenfunctions (compute coefficients).
5. Solve the PDE u_t = u_xx on (0,π) with u(0,t)=0, u_x(π,t)=0, and u(x,0)=x.
6. Prove uniqueness of the PDE solution using an energy method.
7. Determine the long-time limit u(x,t) as t→∞.
8. Solve y'' + y = x with the same boundary conditions using eigenfunction expansion.
9. Verify the expansion solution satisfies boundary conditions term-by-term (justify).
10. Estimate the truncation error of the series using Parseval/Bessel inequality.`,
    },
    {
        name: "Abstract Algebra: Groups, Quotients, and Homomorphisms",
        expected: 10,
        text: `Abstract Algebra: Groups, Quotients, and Homomorphisms
Let G be the group of 2x2 upper triangular matrices over R with positive diagonal entries:
G = { [[a,b],[0,d]] : a>0, d>0, b∈R } under multiplication.

1. Show G is a group under matrix multiplication.
2. Find the center Z(G).
3. Determine the commutator subgroup [G,G].
4. Describe all normal subgroups of the form { [[1,b],[0,1]] } and classify them.
5. Define a homomorphism φ: G → R^2 using logs of diagonal entries; prove it is a surjective homomorphism.
6. Identify ker(φ) and describe the quotient G/ker(φ).
7. Determine whether G is solvable and justify using a derived series.
8. Determine whether G is nilpotent; justify.
9. Find all one-dimensional continuous group homomorphisms from G to (R,+).
10. Decide whether G is isomorphic to a semidirect product; if yes, specify the factors and action.`,
    },
    {
        name: "Probability (Advanced): Joint Distributions and Transformations",
        expected: 10,
        text: `Probability (Advanced): Joint Distributions and Transformations
Let (X,Y) have joint density f(x,y)=c e^{-(x+2y)} on the region x>0, y>0, x>y.

1. Find c.
2. Compute the marginal density f_X(x).
3. Compute the marginal density f_Y(y).
4. Compute P(X > 2).
5. Compute P(Y < 1/2).
6. Compute E[X] and E[Y].
7. Compute E[XY].
8. Compute Cov(X,Y) and Corr(X,Y).
9. Find the conditional density f_{Y|X}(y|x) and its support.
10. Use the transformation U = X - Y, V = Y. Find the joint density f_{U,V}(u,v) and state whether U and V are independent.`,
    },
    {
        name: "Functional Analysis: Norms, Operators, and Convergence",
        expected: 10,
        text: `Functional Analysis: Norms, Operators, and Convergence
Let T: C[0,1] → C[0,1] be defined by (Tf)(x)=∫_0^x f(t) dt.

1. Show T is linear.
2. Compute ||T|| as an operator from (C[0,1], ||·||∞) to itself.
3. Show T is bounded and continuous.
4. Determine whether T is compact (justify).
5. Find the spectrum σ(T) (or characterize it) in the sup-norm setting.
6. Solve (I - T)f = g for a given g in C[0,1] and express f in terms of g.
7. Show that the Neumann series ∑_{n≥0} T^n converges in operator norm and identify its sum.
8. Compute (T^n f)(x) explicitly.
9. Determine whether T has any eigenvalues and eigenfunctions; if yes, find them.
10. Discuss whether T is self-adjoint under the L^2 inner product (and what changes if the space is L^2[0,1]).`,
    },
    {
        name: "Complex Numbers / Fourier: Contours and Fourier Coefficients",
        expected: 10,
        text: `Complex Numbers / Fourier: Contours and Fourier Coefficients
Let f(θ)=ln(2 - 2cos θ) for θ∈(0,2π).

1. Simplify f(θ) using trig identities.
2. Show f is integrable over (0,2π) and identify singular behavior near 0.
3. Compute the average value (1/(2π))∫_0^{2π} f(θ) dθ.
4. Compute the Fourier series of f(θ) (give coefficients explicitly).
5. Use the substitution z=e^{iθ} to convert ∫ f(θ) dθ into a contour integral.
6. Evaluate ∫_0^{2π} cos(nθ) f(θ) dθ for n≥1.
7. Show the resulting coefficients match the Fourier series from (4).
8. Use residues to compute ∫_0^{2π} (1/(2-2cos θ)) dθ.
9. Determine whether the Fourier series converges pointwise everywhere and explain where/how.
10. Use Parseval’s identity to compute ∑_{n=1}^∞ 1/n^2 from your coefficients (outline clearly).`,
    },
    {
        name: "PDE / Vector Calculus: Divergence Theorem and Laplace Equation",
        expected: 10,
        text: `PDE / Vector Calculus: Divergence Theorem and Laplace Equation
Let Ω be the solid region bounded by the paraboloid z = 4 - x^2 - y^2 and the plane z = 0.

1. Describe Ω in cylindrical coordinates.
2. Compute Volume(Ω).
3. Compute ∬_{∂Ω} z dS (surface integral over the boundary).
4. Use the divergence theorem to compute ∬_{∂Ω} F·n dS for F=(x, y, z).
5. Compute ∭_Ω div(F) dV and verify it matches (4).
6. Compute the flux through the paraboloid part only.
7. Compute ∬_{∂Ω} (x^2 + y^2) dS and discuss symmetry to simplify.
8. Solve Laplace’s equation ∇^2 u=0 in Ω under boundary condition u=0 on z=0 and u=1 on the paraboloid, using symmetry assumptions and justify them.
9. Determine whether the boundary-value problem in (8) has a unique solution and why.
10. Compute ∭_Ω (4 - x^2 - y^2) dV and interpret it geometrically.`,
    },
];

for (const [idx, fixture] of fixtures.entries()) {
    const result = detectMultiQuestion(fixture.text);
    const splits = autoSplitQuestions(fixture.text);
    const ok = splits.length === fixture.expected;
    console.log(`\n[${idx + 1}] ${fixture.name}`);
    console.log(`expected=${fixture.expected} actual=${splits.length} confidence=${result.confidence} isMultiple=${result.isMultiple} status=${ok ? "PASS" : "FAIL"}`);
    splits.forEach((s, i) => {
        console.log(`  ${i + 1}. ${s}`);
    });
}
